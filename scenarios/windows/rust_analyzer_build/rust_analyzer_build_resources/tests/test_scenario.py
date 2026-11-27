import importlib
import importlib.util
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NAME = "rust_analyzer_build"
WORKLOAD = "rust_analyzer_build"
PLATFORM = "Windows"
CLASS_NAME = "RustAnalyzerBuild"
LAUNCHER = "invoke.ps1"


class Parameters:
    values = {}

    @classmethod
    def setDefault(cls, module, key, value):
        cls.values.setdefault((module, key), value)

    @classmethod
    def get(cls, module, key):
        return cls.values[(module, key)]


class FrameworkStub(unittest.TestCase):
    def setUp(self):
        self.events.append("measurement-start")

    def tearDown(self):
        self.events.append("measurement-stop")

    def _upload(self, source, destination, **kwargs):
        self.assertTrue(Path(source).is_file())
        self.assertFalse(kwargs["check_modified"])
        self.events.append(("upload", Path(source).name, destination))

    def _remote_make_dir(self, path):
        self.events.append(("mkdir", path))

    def _call(self, command, **kwargs):
        self.events.append(command)
        if self.fail_phase and self.fail_phase in command[1]:
            raise RuntimeError("original phase failure")

    def createPrepStatusControlFile(self, *args):
        self.events.append("prep-status")

    def _copy_data_from_remote(self, *args):
        self.events.append("copy")


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        core = types.ModuleType("core")
        app = types.ModuleType("core.app_scenario")
        app.Scenario = FrameworkStub
        core.app_scenario = app
        params = types.ModuleType("core.parameters")
        params.Params = Parameters
        self.modules = patch.dict(sys.modules, {"core": core, "core.app_scenario": app, "core.parameters": params})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        Parameters.values = {("global", "platform"): PLATFORM}
        spec = importlib.util.spec_from_file_location(NAME, ROOT.parent / f"{NAME}.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def instance(self, platform=PLATFORM):
        Parameters.values[("global", "platform")] = platform
        test = getattr(self.module, CLASS_NAME)()
        test.dut_exec_path = r"R:\custom tools\hobl_bin" if platform == "Windows" else "/tmp/custom tools/hobl_bin"
        test.dut_data_path = r"R:\custom data\hobl_data" if platform == "Windows" else "/tmp/custom data/hobl_data"
        test.result_dir = "results"
        test.events = []
        test.fail_phase = None
        return test

    def test_prep_precedes_measurement_and_teardown_is_idempotent(self):
        test = self.instance()
        test.setUp()
        test.runTest()
        test.tearDown()
        count = len(test.events)
        test.tearDown()
        self.assertEqual(len(test.events), count)
        self.assertLess(test.events.index("prep-status"), test.events.index("measurement-start"))
        self.assertIn("measurement-stop", test.events)
        self.assertEqual(test.events[-1], "copy")
        uploads = [event[1] for event in test.events if isinstance(event, tuple) and event[0] == "upload"]
        self.assertEqual(uploads, ["build.py", LAUNCHER, WORKLOAD + ".json"])
        command = test.command("run")
        self.assertIn(NAME + "-work", command[1])
        self.assertIn(NAME + "_resources", command[1])
        self.assertTrue(all(event[2].endswith(NAME + "_resources")
                            for event in test.events if isinstance(event, tuple) and event[0] == "upload"))

    def test_prep_failure_does_not_start_measurement(self):
        test = self.instance()
        test.fail_phase = "prep "
        with self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.setUp()
        test.doCleanups()
        self.assertNotIn("measurement-start", test.events)
        self.assertNotIn("measurement-stop", test.events)
        self.assertEqual(test.events[-1], "copy")

    def test_linux_platform_rejected_before_remote_setup(self):
        test = self.instance(platform="Linux")
        with self.assertRaisesRegex(ValueError, "Unsupported Rust workload platform: Linux"):
            test.setUp()
        self.assertEqual(test.events, [])
        test.doCleanups()

    def test_package_discovers_one_workload_without_shared_resources(self):
        spec = importlib.util.spec_from_file_location(
            NAME, ROOT.parent / "__init__.py",
            submodule_search_locations=[str(ROOT.parent)],
        )
        registration = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {NAME: registration}):
            spec.loader.exec_module(registration)
            suite = unittest.defaultTestLoader.loadTestsFromModule(registration)
            self.assertEqual(suite.countTestCases(), 1)
            test = next(iter(next(iter(suite))))
            self.assertEqual(test.module, NAME)
            self.assertEqual(test.workload, WORKLOAD)
            self.assertEqual(test.resources, NAME + "_resources")

    def test_scenario_runs_with_only_its_own_package_present(self):
        with tempfile.TemporaryDirectory(prefix="hobl isolated scenario ") as directory:
            package = Path(directory) / NAME
            shutil.copytree(ROOT.parent, package, ignore=shutil.ignore_patterns("__pycache__"))
            runner = package / ROOT.name / "tests" / "test_scenario.py"
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(runner),
                 "ScenarioTests.test_package_discovers_one_workload_without_shared_resources",
                 "ScenarioTests.test_prep_precedes_measurement_and_teardown_is_idempotent"],
                cwd=directory, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_kill_suppresses_framework_process_name_fallback(self):
        test = self.instance()
        test.fail_phase = "kill "
        with self.assertLogs(level="ERROR"):
            self.assertEqual(test.kill(), 0)

    def test_run_failure_is_not_replaced_by_cleanup_failure(self):
        test = self.instance()
        test.setUp()
        test.fail_phase = "run "
        with self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.runTest()
        test.fail_phase = "teardown "
        with self.assertLogs(level="ERROR"):
            test.tearDown()
        self.assertIn("measurement-stop", test.events)
        self.assertEqual(test.events[-1], "copy")

    def test_cleanup_failure_after_success_is_reported(self):
        test = self.instance()
        test.setUp()
        test.runTest()
        test.fail_phase = "teardown "
        with self.assertLogs(level="ERROR"), self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.tearDown()
        self.assertEqual(test.events[-1], "copy")


if __name__ == "__main__":
    unittest.main()
