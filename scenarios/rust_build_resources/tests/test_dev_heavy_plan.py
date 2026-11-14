import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = [
    "fast_api", "foundrylocal", "llvm", "mlperf", "net_aspire", "nodejs",
    "ollama", "opencv_build", "pytorch_inf", "spring_petclinic", "vscode",
    "rust_analyzer_build", "nushell_build",
]


@unittest.skipUnless(os.name == "nt" and shutil.which("pwsh"), "Windows HOBL host with PowerShell")
class DeveloperPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hobl developer plan ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        (self.directory / "testplans").mkdir()
        self.plan = self.directory / "testplans" / "hobl_dev_heavy.ps1"
        shutil.copyfile(ROOT / "testplans" / self.plan.name, self.plan)
        self.profile = self.directory / "test device.ini"
        self.profile.write_text("[global]\n", encoding="utf-8")
        self.log = self.directory / "calls.jsonl"
        recorder = self.directory / "record.py"
        recorder.write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "with Path(__file__).with_name('calls.jsonl').open('a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "scenario = sys.argv[sys.argv.index('-s') + 1]\n"
            "sys.exit(7 if scenario == os.environ.get('HOBL_TEST_FAIL_SCENARIO') else 0)\n",
            encoding="utf-8",
        )
        (self.directory / "hobl.cmd").write_text(
            f'@echo off\n@"{sys.executable}" "{recorder}" %*\n@exit /b %errorlevel%\n',
            encoding="utf-8",
        )

    def run_plan(self, platform, fail=""):
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(self.plan),
             "-Profile", str(self.profile), "-Platform", platform],
            env={**os.environ, "HOBL_TEST_FAIL_SCENARIO": fail},
            capture_output=True, text=True, timeout=60,
        )
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return result, calls

    def test_platform_plans_run_existing_and_rust_workloads_independently(self):
        for platform, prefix, folder in (("Windows", "", "windows"), ("MacOS", "mac_", "macos")):
            with self.subTest(platform=platform):
                self.log.unlink(missing_ok=True)
                result, calls = self.run_plan(platform)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                names = [prefix + name for name in SCENARIOS]
                self.assertEqual(calls, [["-p", str(self.profile), "-s", name] for name in names])
                for name in names:
                    location = ROOT / "scenarios" / folder / name
                    self.assertTrue(location.with_suffix(".py").is_file() or
                                    (location / "__init__.py").is_file(), name)

    def test_failure_stops_plan_and_reports_failed_workload(self):
        result, calls = self.run_plan("Windows", fail="rust_analyzer_build")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Developer workload rust_analyzer_build failed with exit code 7",
                      result.stdout + result.stderr)
        self.assertEqual([call[-1] for call in calls], SCENARIOS[:-1])


if __name__ == "__main__":
    unittest.main()
