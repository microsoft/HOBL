import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build", ROOT / "build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def test_linux_prep_rejected_before_creating_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(
                workload="nushell_build", toolchain=None,
                work_root=str(root / "work"), data_dir=str(root / "data"),
            )
            with patch.object(build.platform, "system", return_value="Linux"), \
                    patch.object(build, "native_environment") as native:
                with self.assertRaisesRegex(RuntimeError, "Unsupported operating system: Linux"):
                    build.prepare(args)
                native.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_cli_rejects_linux_scenario_names(self):
        with tempfile.TemporaryDirectory() as directory:
            for workload in build.WORKLOADS:
                with self.subTest(workload=workload):
                    result = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "build.py"), "prep",
                         "--workload", workload, "--scenario", "lnx_" + workload,
                         "--work-root", str(Path(directory) / "work"),
                         "--data-dir", str(Path(directory) / "data")],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("scenario must be one of the registered HOBL scenario names",
                                  result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows command-line quoting")
    def test_cmd_batch_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="hobl command ") as directory:
            batch = Path(directory) / "developer tools.cmd"
            batch.write_text("@echo off\nset HOBL_QUOTE_TEST=passed\n", encoding="ascii")
            output = build.capture(
                f'"{os.environ["COMSPEC"]}" /d /s /c "call "{batch}" >nul && set HOBL_QUOTE_TEST"'
            )
            self.assertEqual(output, "HOBL_QUOTE_TEST=passed")

    def test_environment_removes_external_overrides_not_project_config(self):
        env = build.build_environment(Path("owned"), "1.100.0", {
            "PATH": "native", "CARGO_PROFILE_RELEASE_LTO": "false",
            "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER": "other",
            "RUSTFLAGS": "-C opt-level=0", "RUSTC_WRAPPER": "sccache", "CC": "other",
        })
        self.assertEqual(env["PATH"], "native")
        self.assertEqual(env["RUSTUP_TOOLCHAIN"], "1.100.0")
        self.assertNotIn("RUSTFLAGS", env)
        self.assertNotIn("RUSTC_WRAPPER", env)
        self.assertNotIn("CARGO_PROFILE_RELEASE_LTO", env)
        self.assertNotIn("CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER", env)
        self.assertNotIn("CC", env)

    def test_teardown_only_removes_owned_build_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target").mkdir()
            (root / "source").mkdir()
            (root / "cargo-home").mkdir()
            with self.assertRaises(RuntimeError):
                build.remove_target(root, "nushell_build")
            build.write_json(root / ".hobl-rust-workload.json", {"workload": "nushell_build"})
            with self.assertRaises(RuntimeError):
                build.remove_target(root, "rust_analyzer_build")
            build.remove_target(root, "nushell_build")
            build.remove_target(root, "nushell_build")
            self.assertTrue((root / "source").is_dir())
            self.assertTrue((root / "cargo-home").is_dir())
            self.assertFalse((root / "target").exists())

    def test_concurrent_workload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with build.locked(root):
                with self.assertRaises(RuntimeError):
                    with build.locked(root):
                        self.fail("Concurrent work acquired the lock")
            self.assertFalse((root / "active.lock").exists())

    def test_build_failure_is_not_success_shaped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build.execute_build(
                [sys.executable, "-c", "raise SystemExit(7)"],
                root, dict(os.environ), root, root / "failure", 10,
            )
            self.assertEqual(result["exit_code"], 7)
            self.assertGreater(result["scenario_runtime"], 0)
            self.assertNotIn("verified", result)

    def test_timeout_and_cancel_stop_only_owned_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [sys.executable, "-c", "import time; time.sleep(20)"]
            with self.assertRaises(TimeoutError):
                build.execute_build(command, root, dict(os.environ), root, root / "timeout", 0.2)
            (root / "cancel").touch()
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                build.execute_build(command, root, dict(os.environ), root, root / "cancelled", 10)

    def test_artifacts_reject_cached_or_failed_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cargo.jsonl"
            for fresh, success, valid in ((True, True, False), (False, False, False), (False, True, True)):
                path.write_text("\n".join(json.dumps(message) for message in (
                    {"reason": "compiler-artifact", "fresh": fresh},
                    {"reason": "build-finished", "success": success},
                )))
                if valid:
                    self.assertEqual(build.cargo_artifacts(path), 1)
                else:
                    with self.assertRaises(RuntimeError):
                        build.cargo_artifacts(path)


if __name__ == "__main__":
    unittest.main()
