import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


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
        spec = importlib.util.spec_from_file_location("rust_scenario", ROOT / "scenario.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        Parameters.values = {("global", "platform"): "Windows"}

    def instance(self, workload="nushell_build", module=None, platform="Windows"):
        name = module or workload
        self.module.defaults(name)
        Parameters.values[("global", "platform")] = platform
        cls = type("Workload", (self.module.RustBuildScenario,), {"module": name, "workload": workload})
        test = cls()
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
        self.assertEqual(uploads, ["build.py", "invoke.ps1", "invoke.sh", "nushell_build.json"])
        command = next(event for event in test.events if isinstance(event, list) and "-Phase run " in event[1])
        self.assertIn(r'R:\custom tools\hobl_bin\nushell_build-work', command[1])

    def test_prep_failure_does_not_start_measurement(self):
        test = self.instance()
        test.fail_phase = "-Phase prep "
        with self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.setUp()
        test.doCleanups()
        self.assertNotIn("measurement-start", test.events)
        self.assertNotIn("measurement-stop", test.events)
        self.assertEqual(test.events[-1], "copy")

    def test_distinct_workloads_and_mac_names_are_preserved(self):
        first = self.instance()
        first.setUp()
        second = self.instance("rust_analyzer_build", "mac_rust_analyzer_build", "MacOS")
        second.setUp()
        windows = first.command("run")
        mac = second.command("run")
        self.assertIn("-Workload nushell_build", windows[1])
        self.assertIn("-Scenario nushell_build", windows[1])
        self.assertEqual(mac[0], "sh")
        self.assertIn("run rust_analyzer_build mac_rust_analyzer_build", mac[1])
        self.assertIn("mac_rust_analyzer_build-work", mac[1])
        first.tearDown()
        second.tearDown()

    def test_registered_modules_discover_one_independent_workload_each(self):
        resources = types.ModuleType("scenarios.rust_build_resources")
        resources.scenario = self.module
        with patch.dict(sys.modules, {"scenarios.rust_build_resources": resources}):
            for platform, prefix in (("windows", ""), ("macos", "mac_"), ("linux", "lnx_")):
                for workload in ("rust_analyzer_build", "nushell_build"):
                    name = prefix + workload
                    with self.subTest(scenario=name):
                        path = ROOT.parent / platform / (name + ".py")
                        spec = importlib.util.spec_from_file_location(f"scenarios.{platform}.{name}", path)
                        registration = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(registration)
                        suite = unittest.defaultTestLoader.loadTestsFromModule(registration)
                        self.assertEqual(suite.countTestCases(), 1)
                        test = next(iter(next(iter(suite))))
                        self.assertEqual(test.module, name)
                        self.assertEqual(test.workload, workload)
                        self.assertEqual(Parameters.get(name, "toolchain"), "1.100.0")

    def test_kill_suppresses_framework_process_name_fallback(self):
        test = self.instance()
        test.fail_phase = "-Phase kill "
        with self.assertLogs(level="ERROR"):
            self.assertEqual(test.kill(), 0)

    def test_run_failure_is_not_replaced_by_cleanup_failure(self):
        test = self.instance()
        test.setUp()
        test.fail_phase = "-Phase run "
        with self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.runTest()
        test.fail_phase = "-Phase teardown "
        with self.assertLogs(level="ERROR"):
            test.tearDown()
        self.assertIn("measurement-stop", test.events)
        self.assertEqual(test.events[-1], "copy")

    def test_cleanup_failure_after_success_is_reported(self):
        test = self.instance()
        test.setUp()
        test.runTest()
        test.fail_phase = "-Phase teardown "
        with self.assertLogs(level="ERROR"), self.assertRaisesRegex(RuntimeError, "original phase failure"):
            test.tearDown()
        self.assertEqual(test.events[-1], "copy")


if __name__ == "__main__":
    unittest.main()
