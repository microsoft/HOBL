from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import psutil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uv", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--loops", type=int, default=5)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--reload-mode",
        choices=("none", "managed", "external"),
        default="none",
        help=(
            "'managed' owns the reload server in this process tree; "
            "'external' measures a foreground server already running on --port"
        ),
    )
    return parser.parse_args()


def app_python(project: Path) -> Path:
    relative = (
        Path(".venv/Scripts/python.exe")
        if os.name == "nt"
        else Path(".venv/bin/python")
    )
    return project / relative


def request_build(port: int) -> int | None:
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"Connection": "close"},
        )
        with urllib.request.urlopen(request, timeout=0.25) as response:
            return json.load(response)["build"]
    except (
        ConnectionError,
        TimeoutError,
        urllib.error.HTTPError,
        urllib.error.URLError,
    ):
        return None


def wait_for_build(port: int, expected: int, timeout: float) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if request_build(port) == expected:
            return
        time.sleep(0.05)
    raise TimeoutError(
        f"Server on port {port} did not report build {expected} within {timeout}s"
    )


def ensure_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(
                f"Port {port} is already in use; cannot measure startup"
            ) from error


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return
    processes = [*parent.children(recursive=True), parent]
    for current in reversed(processes):
        try:
            current.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(processes, timeout=10)
    for current in alive:
        try:
            current.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=5)


def server_command(python: Path, port: int) -> list[str]:
    return [
        str(python),
        "-m",
        "fastapi",
        "dev",
        "app/main.py",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--reload-dir",
        "app",
    ]


def start_server(
    project: Path,
    python: Path,
    port: int,
    environment: dict[str, str],
    log: Any,
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        server_command(python, port),
        cwd=project,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def append_result(
    results: list[dict[str, Any]],
    phase: str,
    loop: int,
    started: float,
    log: str,
    exit_code: int = 0,
) -> None:
    results.append(
        {
            "phase": phase,
            "loop": loop,
            "seconds": round(time.perf_counter() - started, 3),
            "exit_code": exit_code,
            "log": log,
        }
    )


def measure_syncs(
    args: argparse.Namespace,
    project: Path,
    output: Path,
    environment: dict[str, str],
    results: list[dict[str, Any]],
) -> Path:
    venv = project / ".venv"
    for loop in range(1, args.loops + 1):
        if venv.exists():
            shutil.rmtree(venv)
        log_name = f"sync-{loop}.log"
        started = time.perf_counter()
        with (output / log_name).open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [
                    str(args.uv),
                    "sync",
                    "--frozen",
                    "--offline",
                    "--python",
                    str(args.python),
                ],
                cwd=project,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        append_result(
            results, "sync", loop, started, log_name, completed.returncode
        )
        if completed.returncode:
            raise RuntimeError(f"sync failed; see {output / log_name}")
    python = app_python(project)
    if not python.is_file():
        raise RuntimeError(f"uv sync did not create the app interpreter: {python}")
    return python


def measure_server_startups(
    args: argparse.Namespace,
    project: Path,
    python: Path,
    output: Path,
    environment: dict[str, str],
    results: list[dict[str, Any]],
) -> None:
    for loop in range(1, args.loops + 1):
        port = args.port + loop if args.reload_mode == "external" else args.port
        log_name = f"server-start-{loop}.log"
        with (output / log_name).open("w", encoding="utf-8") as log:
            ensure_port_available(port)
            started = time.perf_counter()
            server = start_server(project, python, port, environment, log)
            try:
                wait_for_build(port, 0, args.timeout)
                if server.poll() is not None:
                    raise RuntimeError(
                        f"Server process exited during startup; see "
                        f"{output / log_name}"
                    )
                append_result(
                    results, "server-start", loop, started, log_name
                )
            finally:
                stop_process_tree(server)
        time.sleep(0.25)


def measure_reloads(
    args: argparse.Namespace,
    project: Path,
    python: Path,
    output: Path,
    environment: dict[str, str],
    version_file: Path,
    results: list[dict[str, Any]],
) -> None:
    if args.reload_mode == "none":
        return
    if args.reload_mode == "managed" and os.name == "nt":
        raise RuntimeError(
            "Managed reload cannot be automated reliably on Windows because "
            "Uvicorn broadcasts CTRL_C_EVENT to its console. Start "
            "fast_api_app_reload_server.ps1 in a foreground terminal and "
            "rerun with reload_mode=external."
        )

    server = None
    log = None
    if args.reload_mode == "managed":
        log = (output / "reload-server.log").open("w", encoding="utf-8")
        server = start_server(
            project, python, args.port, environment, log
        )

    try:
        wait_for_build(args.port, 0, args.timeout)
        for loop in range(1, args.loops + 1):
            started = time.perf_counter()
            version_file.write_text(
                f"BUILD_ID = {loop}\n# {'x' * loop}\n",
                encoding="utf-8",
            )
            wait_for_build(args.port, loop, args.timeout)
            append_result(
                results,
                "reload",
                loop,
                started,
                "reload-server.log"
                if args.reload_mode == "managed"
                else "external foreground server",
            )
            time.sleep(0.25)
    finally:
        if server is not None:
            stop_process_tree(server)
        if log is not None:
            log.close()


def run_command(
    phase: str,
    loop: int,
    python: Path,
    arguments: list[str],
    project: Path,
    output: Path,
    environment: dict[str, str],
    results: list[dict[str, Any]],
) -> None:
    log_name = f"{phase}-{loop}.log"
    started = time.perf_counter()
    with (output / log_name).open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            [str(python), *arguments],
            cwd=project,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    append_result(
        results, phase, loop, started, log_name, completed.returncode
    )
    if completed.returncode:
        raise RuntimeError(f"{phase} failed; see {output / log_name}")


def summarize(
    results: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for result in results:
        grouped[result["phase"]].append(result["seconds"])
    return {
        phase: {
            "median": round(statistics.median(values), 3),
            "mean": round(statistics.mean(values), 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }
        for phase, values in grouped.items()
    }


def main() -> int:
    args = parse_args()
    if args.loops < 1:
        raise ValueError("--loops must be at least 1")
    if args.reload_mode == "managed" and os.name == "nt":
        raise RuntimeError(
            "Managed reload cannot be automated reliably on Windows because "
            "Uvicorn broadcasts CTRL_C_EVENT to its console. Start "
            "fast_api_app_reload_server.ps1 in a foreground terminal and "
            "rerun with reload_mode=external."
        )
    if not args.uv.is_file():
        raise FileNotFoundError(f"uv executable not found: {args.uv}")
    if not args.python.is_file():
        raise FileNotFoundError(f"Python executable not found: {args.python}")

    project = Path(__file__).resolve().parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version_file = project / "app" / "version.py"
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["NO_COLOR"] = "1"
    results: list[dict[str, Any]] = []

    version_file.write_text("BUILD_ID = 0\n", encoding="utf-8")
    try:
        if args.reload_mode == "external":
            python = app_python(project)
            if not python.is_file():
                raise RuntimeError(
                    "External reload mode requires an existing app venv. "
                    "Run the workload once with reload_mode=none, then start "
                    "the foreground reload server."
                )
        else:
            python = measure_syncs(
                args, project, output, environment, results
            )
        measure_server_startups(
            args, project, python, output, environment, results
        )
        measure_reloads(
            args,
            project,
            python,
            output,
            environment,
            version_file,
            results,
        )
        version_file.write_text("BUILD_ID = 0\n", encoding="utf-8")
        for loop in range(1, args.loops + 1):
            run_command(
                "import-openapi",
                loop,
                python,
                [
                    "-c",
                    "from app.main import app; schema=app.openapi(); "
                    "assert len(schema['paths']) == 3",
                ],
                project,
                output,
                environment,
                results,
            )
            run_command(
                "app-test",
                loop,
                python,
                ["-m", "pytest", "-q"],
                project,
                output,
                environment,
                results,
            )
    finally:
        version_file.write_text("BUILD_ID = 0\n", encoding="utf-8")

    summary = summarize(results)
    metadata = {
        "python": platform.python_version(),
        "base_python": str(args.python),
        "app_python": str(app_python(project)),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "project": str(project),
        "reload_mode": args.reload_mode,
        "loops": args.loops,
        "scenario_runtime": round(
            summary["server-start"]["median"]
            + summary["import-openapi"]["median"]
            + summary["app-test"]["median"],
            3,
        ),
    }
    with (output / "iterations.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["phase", "loop", "seconds", "exit_code", "log"],
        )
        writer.writeheader()
        writer.writerows(results)
    (output / "results.json").write_text(
        json.dumps(
            {"metadata": metadata, "results": results, "summary": summary},
            indent=2,
        ),
        encoding="utf-8",
    )
    metrics: list[tuple[str, str | float]] = [
        ("scenario_runtime", metadata["scenario_runtime"]),
        ("server_start_time", summary["server-start"]["median"]),
        ("import_openapi_time", summary["import-openapi"]["median"]),
        ("app_test_time", summary["app-test"]["median"]),
        ("architecture", platform.machine()),
    ]
    if "sync" in summary:
        metrics.insert(1, ("sync_time", summary["sync"]["median"]))
    if "reload" in summary:
        metrics.append(("reload_time", summary["reload"]["median"]))
    with (output / "metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        csv.writer(file).writerows(metrics)
    print(json.dumps({"metadata": metadata, "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
