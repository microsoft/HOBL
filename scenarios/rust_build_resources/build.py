# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.

"""Clean, offline Cargo release builds, shared by two independent HOBL workloads."""

import argparse
import contextlib
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import uuid


WORKLOADS = ("rust_analyzer_build", "nushell_build")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def capture(command, **kwargs):
    arguments = command if isinstance(command, str) else [str(arg) for arg in command]
    try:
        return subprocess.check_output(
            arguments, text=True, encoding="utf-8",
            errors="replace", stderr=subprocess.STDOUT, **kwargs
        ).strip()
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Command failed ({error.returncode}): {arguments}\n{error.output}") from error


def architecture():
    machine = os.environ.get("PROCESSOR_ARCHITEW6432", platform.machine()).lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    raise RuntimeError(f"Unsupported architecture: {machine}")


def host_triple():
    arch = {"x64": "x86_64", "arm64": "aarch64"}[architecture()]
    suffix = {
        "Windows": "pc-windows-msvc",
        "Darwin": "apple-darwin",
        "Linux": "unknown-linux-gnu",
    }.get(platform.system())
    if suffix is None:
        raise RuntimeError(f"Unsupported operating system: {platform.system()}")
    return f"{arch}-{suffix}"


def native_environment():
    env = dict(os.environ)
    if os.name == "nt":
        vswhere = shutil.which("vswhere")
        if not vswhere:
            installer = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio" / "Installer"
            vswhere = str(installer / "vswhere.exe")
        if not Path(vswhere).is_file():
            raise RuntimeError("Visual Studio Installer/vswhere is missing. Install native C++ build tools.")
        component = "Microsoft.VisualStudio.Component.VC.Tools." + (
            "ARM64" if architecture() == "arm64" else "x86.x64"
        )
        vs_path = capture([vswhere, "-latest", "-products", "*", "-requires", component,
                           "-property", "installationPath"])
        devcmd = Path(vs_path) / "Common7" / "Tools" / "VsDevCmd.bat"
        if not vs_path or not devcmd.is_file():
            raise RuntimeError("A Visual Studio installation with VsDevCmd.bat is required.")
        arch = architecture()
        command = f'call "{devcmd}" -no_logo -arch={arch} -host_arch={arch} >nul && set'
        # cmd.exe does not implement the C-runtime backslash/quote escaping used by list2cmdline.
        output = capture(f'"{os.environ["COMSPEC"]}" /d /s /c "{command}"')
        for line in output.splitlines():
            key, sep, value = line.partition("=")
            if sep and key and not key.startswith("="):
                env[key.upper()] = value
        # Windows environment keys are case-insensitive, including PATH.
        env = {key.upper(): value for key, value in env.items()}
        print(f"Visual Studio: {vs_path}", flush=True)
        for tool in ("cl.exe", "link.exe", "rc.exe"):
            found = shutil.which(tool, path=env["PATH"])
            if not found:
                raise RuntimeError(f"Native {tool} missing after VsDevCmd: {vs_path}")
            print(f"{tool}: {found}", flush=True)
    else:
        if not shutil.which("cc"):
            raise RuntimeError("A native C compiler is required (Xcode Command Line Tools or GCC/Clang).")
    return env


def build_environment(root, toolchain, native):
    env = {
        key: value for key, value in native.items()
        if not key.upper().startswith(("CARGO_", "RUST", "SCCACHE_"))
        and key.upper() not in ("CC", "CXX", "AR", "CFLAGS", "CXXFLAGS", "LDFLAGS")
    }
    env.update({
        "CARGO_HOME": str(root / "cargo-home"),
        "RUSTUP_HOME": str(root / "rustup-home"),
        "RUSTUP_TOOLCHAIN": toolchain,
        "CARGO_TARGET_DIR": str(root / "target"),
        "CARGO_TERM_COLOR": "never",
    })
    return env


def assert_source(source, revision, env):
    if capture(["git", "rev-parse", "HEAD"], cwd=source, env=env) != revision:
        raise RuntimeError("Source revision differs from the pinned workload.")
    if capture(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=source, env=env):
        raise RuntimeError("Source checkout is dirty; refusing an unrepeatable build.")
    for parent in source.parents:
        for name in ("config", "config.toml"):
            if (parent / ".cargo" / name).exists():
                raise RuntimeError(f"Ancestor Cargo configuration would contaminate the build: {parent}")


def assert_owned(root, name):
    marker = root / ".hobl-rust-workload.json"
    if not marker.is_file() or json.loads(marker.read_text()) != {"workload": name}:
        raise RuntimeError(f"Not an owned {name} work directory: {root}")


def remove_target(root, name):
    assert_owned(root, name)
    target = root / "target"
    if target.is_symlink() or target.resolve().parent != root.resolve():
        raise RuntimeError("Refusing to remove a redirected build-output directory.")
    if target.exists():
        shutil.rmtree(target)


@contextlib.contextmanager
def locked(root):
    lock = root / "active.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f"Workload already active, or previous process interrupted: {lock}") from None
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(fd)
        lock.unlink()


def stop_owned_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=30)


def execute_build(command, source, env, root, prefix, timeout):
    usage_before = None
    if os.name != "nt":
        import resource
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with prefix.with_suffix(".stdout.jsonl").open("w", encoding="utf-8") as stdout, \
            prefix.with_suffix(".stderr.log").open("w", encoding="utf-8") as stderr:
        started = time.perf_counter()
        process = subprocess.Popen(
            command, cwd=source, env=env, stdout=stdout, stderr=stderr,
            start_new_session=os.name != "nt",
        )
        try:
            while process.poll() is None:
                if (root / "cancel").exists():
                    raise RuntimeError("Build cancelled by HOBL.")
                if time.perf_counter() - started > timeout:
                    raise TimeoutError(f"Build exceeded {timeout} seconds.")
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
            elapsed = time.perf_counter() - started
        finally:
            stop_owned_process(process)
    result = {"build_time": elapsed, "scenario_runtime": elapsed, "exit_code": process.returncode}
    if usage_before is not None:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(
            build_user=usage.ru_utime - usage_before.ru_utime,
            build_sys=usage.ru_stime - usage_before.ru_stime,
        )
        result["build_cputime"] = result["build_user"] + result["build_sys"]
        result["max_child_rss_bytes"] = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return result


def cargo_artifacts(path):
    compiled = 0
    finished = False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        message = json.loads(line)
        if message.get("reason") == "compiler-artifact" and not message["fresh"]:
            compiled += 1
        if message.get("reason") == "build-finished":
            finished = message["success"]
    if not finished or compiled == 0:
        raise RuntimeError("Cargo did not report a successful build with newly compiled artifacts.")
    return compiled


def inventory():
    result = {
        "os": platform.platform(), "architecture": architecture(),
        "logical_cpus": os.cpu_count(), "python": sys.version,
        "runner_label": os.environ.get("HOBL_RUNNER_LABEL"),
        "runner_image": os.environ.get("ImageOS"),
        "runner_image_version": os.environ.get("ImageVersion"),
    }
    if os.name == "nt":
        command = ["powershell", "-NoProfile", "-Command",
                   "@{cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
                   "NumberOfLogicalProcessors; memory=(Get-CimInstance Win32_ComputerSystem)."
                   "TotalPhysicalMemory} | ConvertTo-Json -Depth 4"]
    elif sys.platform == "darwin":
        command = ["sysctl", "machdep.cpu.brand_string", "hw.memsize", "hw.ncpu"]
    else:
        command = ["lscpu"]
        result["meminfo"] = Path("/proc/meminfo").read_text()
    result["hardware"] = capture(command)
    return result


def load_context(args):
    config_path = Path(__file__).with_name(f"{args.workload}.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    toolchain = args.toolchain or config["toolchain"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", toolchain):
        raise ValueError("toolchain must be an exact stable release, such as 1.100.0")
    root = Path(args.work_root).resolve()
    data = Path(args.data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    return config, toolchain, root, data


def prepare(args):
    config, toolchain, root, data = load_context(args)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ".hobl-rust-workload.json"
    if not marker.exists():
        if any(root.iterdir()):
            raise RuntimeError("Prep requires an empty directory or this workload's existing owned directory.")
        write_json(marker, {"workload": config["name"]})
    assert_owned(root, config["name"])
    with locked(root):
        env = build_environment(root, toolchain, native_environment())
        rustup = shutil.which("rustup")
        if not rustup:
            candidate = Path.home() / ".cargo" / "bin" / ("rustup.exe" if os.name == "nt" else "rustup")
            if not candidate.is_file():
                raise RuntimeError("rustup is missing; install rustup before preparing this workload.")
            rustup = str(candidate)
        subprocess.run([rustup, "toolchain", "install", toolchain, "--profile", "minimal"], env=env, check=True)
        cargo = capture([rustup, "which", "--toolchain", toolchain, "cargo"], env=env)
        rustc = capture([rustup, "which", "--toolchain", toolchain, "rustc"], env=env)
        rustdoc = str(Path(rustc).with_name("rustdoc.exe" if os.name == "nt" else "rustdoc"))
        env["RUSTC"], env["RUSTDOC"] = rustc, rustdoc
        version = capture([rustc, "-vV"], env=env)
        if f"host: {host_triple()}" not in version:
            raise RuntimeError(f"Rust compiler is not native to this runner:\n{version}")
        source = root / "source"
        repository = args.repository or config["repository"]
        if not source.exists():
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "remote", "add", "origin", repository], check=True)
            subprocess.run(["git", "-C", str(source), "fetch", "--quiet", "--depth=1", "origin",
                            config["revision"]], check=True)
            subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "--detach", "FETCH_HEAD"], check=True)
        assert_source(source, config["revision"], env)
        subprocess.run([cargo, "fetch", "--locked", "--target", host_triple()], cwd=source, env=env, check=True)
        target_config = tomllib.loads((source / ".cargo" / "config.toml").read_text())
        configured_linker = target_config.get("target", {}).get(host_triple(), {}).get("linker")
        receipt = {
            "workload": config["name"], "revision": config["revision"],
            "repository": capture(["git", "remote", "get-url", "origin"], cwd=source),
            "toolchain": toolchain, "host_triple": host_triple(), "rustc_version": version,
            "cargo_version": capture([cargo, "-V"], env=env),
            "tools": {"cargo": cargo, "rustc": rustc, "rustdoc": rustdoc},
            "tool_hashes": {name: digest(path) for name, path in
                            (("cargo", cargo), ("rustc", rustc), ("rustdoc", rustdoc))},
            "lock_sha256": digest(source / "Cargo.lock"),
            "recipe_sha256": digest(Path(__file__).with_name(f"{args.workload}.json")),
            "configured_linker": configured_linker,
            "linker_policy": configured_linker or ("link.exe" if os.name == "nt" else "toolchain default"),
            "inventory": inventory(),
        }
        write_json(root / "prepared.json", receipt)
        write_json(data / "prepared.json", receipt)
        print(f"Prepared {config['name']}: {config['revision']}, native {host_triple()}", flush=True)


def run(args):
    config, toolchain, root, data = load_context(args)
    assert_owned(root, config["name"])
    with locked(root):
        (root / "cancel").unlink(missing_ok=True)
        receipt = json.loads((root / "prepared.json").read_text())
        if (receipt["workload"], receipt["toolchain"], receipt["host_triple"]) != (
                config["name"], toolchain, host_triple()):
            raise RuntimeError("Prep receipt does not match the requested workload/toolchain/platform.")
        if receipt["recipe_sha256"] != digest(Path(__file__).with_name(f"{args.workload}.json")):
            raise RuntimeError("Workload recipe changed. Re-run prep.")
        env = build_environment(root, toolchain, native_environment())
        for name, path in receipt["tools"].items():
            if not Path(path).is_file() or digest(path) != receipt["tool_hashes"][name]:
                raise RuntimeError(f"Prepared {name} changed or disappeared. Re-run prep.")
        env["RUSTC"], env["RUSTDOC"] = receipt["tools"]["rustc"], receipt["tools"]["rustdoc"]
        linker_dir = Path(receipt["tools"]["rustc"]).parent.parent / "lib" / "rustlib" / host_triple() / "bin"
        path_key = "PATH"
        env[path_key] = str(linker_dir) + os.pathsep + str(Path(receipt["tools"]["rustc"]).parent) + os.pathsep + env[path_key]
        source = root / "source"
        assert_source(source, config["revision"], env)
        if digest(source / "Cargo.lock") != receipt["lock_sha256"]:
            raise RuntimeError("Cargo.lock changed after prep.")
        remove_target(root, config["name"])
        jobs = args.jobs or os.cpu_count()
        command = [receipt["tools"]["cargo"], "build", "--frozen", "--release",
                   "-p", config["package"], "--bin", config["binary"],
                   "--jobs", str(jobs), "--timings", "--message-format=json"]
        token = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
        prefix = data / token
        csv_path = data / f"{args.scenario}_results.csv"
        csv_path.unlink(missing_ok=True)
        print(f"Timed command: {' '.join(command)}", flush=True)
        result = execute_build(command, source, env, root, prefix, args.timeout)
        result.update(
            workload=config["name"], scenario=args.scenario, sample=args.sample,
            revision=config["revision"], toolchain=toolchain, host_triple=host_triple(),
            architecture=architecture(), jobs=jobs, command=command,
            harness_sha256=digest(__file__), lock_sha256=receipt["lock_sha256"],
            linker_policy=receipt["linker_policy"], target_was_empty=True,
        )
        write_json(prefix.with_suffix(".json"), result)
        if result["exit_code"] != 0:
            tail = prefix.with_suffix(".stderr.log").read_text(encoding="utf-8")[-12000:]
            raise RuntimeError(f"Cargo failed with exit code {result['exit_code']}:\n{tail}")
        result["compiled_artifacts"] = cargo_artifacts(prefix.with_suffix(".stdout.jsonl"))
        assert_source(source, config["revision"], env)
        report = root / "target" / "cargo-timings" / "cargo-timing.html"
        shutil.copyfile(report, prefix.with_suffix(".timings.html"))
        binary = root / "target" / "release" / (config["binary"] + (".exe" if os.name == "nt" else ""))
        result["binary_sha256"] = digest(binary)
        result["binary_bytes"] = binary.stat().st_size
        result["smoke_output"] = capture([binary, "--version"], env=env, timeout=60)
        if config["binary"] == "nu":
            value = capture([binary, "--no-config-file", "-c", "1 + 1"], env=env, timeout=60)
            if value != "2":
                raise RuntimeError(f"Nushell smoke test returned {value!r} instead of '2'.")
        result["verified"] = True
        write_json(prefix.with_suffix(".json"), result)
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            for key in ("scenario_runtime", "build_time", "architecture", "jobs",
                        "build_user", "build_sys", "build_cputime"):
                if key in result:
                    writer.writerow([key, result[key]])
        print("========================================", flush=True)
        print(f"{args.scenario} Build Metrics Summary", flush=True)
        print(f"scenario_runtime: {result['scenario_runtime']:.6f} seconds", flush=True)
        print(f"build_time: {result['build_time']:.6f} seconds", flush=True)
        print(f"architecture: {architecture()}; jobs: {jobs}; sample: {args.sample}", flush=True)
        print("========================================", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prep", "run", "teardown", "kill"))
    parser.add_argument("--workload", choices=WORKLOADS, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--toolchain")
    parser.add_argument("--repository")
    parser.add_argument("--jobs", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--sample", type=int, default=1)
    args = parser.parse_args()
    if not re.fullmatch(r"(?:mac_|lnx_)?(?:rust_analyzer_build|nushell_build)", args.scenario):
        parser.error("scenario must be one of the registered HOBL scenario names")
    if not 0 <= args.jobs <= 4096 or not 1 <= args.timeout <= 2400 or args.sample < 1:
        parser.error("invalid jobs, timeout or sample")
    if args.phase == "prep":
        prepare(args)
    elif args.phase == "run":
        run(args)
    else:
        config, _, root, _ = load_context(args)
        assert_owned(root, config["name"])
        if args.phase == "kill":
            if (root / "active.lock").exists():
                (root / "cancel").touch()
        else:
            with locked(root):
                remove_target(root, config["name"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f" ERROR - {error}", file=sys.stderr, flush=True)
        sys.exit(1)
