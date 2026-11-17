# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.

"""HOBL lifecycle for the nushell_build workload."""

import logging
import ntpath
from pathlib import Path

import core.app_scenario
from core.parameters import Params


class NushellBuild(core.app_scenario.Scenario):
    module = __module__.split(".")[-1]
    workload = "nushell_build"
    prep_version = "2"
    resources = module + "_resources"

    Params.setDefault(module, "loops", "1")
    Params.setDefault(module, "jobs", "0")
    Params.setDefault(module, "toolchain", "1.100.0")

    def command(self, phase, sample=1):
        if self.platform.lower() != "windows":
            raise ValueError(f"Unsupported Rust workload platform: {self.platform}")
        resources = ntpath.join(self.dut_exec_path, self.resources)
        work = ntpath.join(self.dut_exec_path, self.module + "-work")
        values = [phase, self.workload, self.module, work, self.dut_data_path, self.toolchain]
        if any('"' in value or "\n" in value or "\r" in value for value in values):
            raise ValueError("Invalid quote or newline in workload arguments.")
        return ["pwsh", f'-NoProfile -NonInteractive -File "{resources}\\invoke.ps1" '
                f'-Phase {phase} -Workload {self.workload} -Scenario {self.module} '
                f'-WorkRoot "{work}" -DataDir "{self.dut_data_path}" '
                f'-Toolchain "{self.toolchain}" -Jobs {self.jobs} -Sample {sample}']

    def setUp(self):
        self.platform = Params.get("global", "platform")
        self.loops = int(Params.get(self.module, "loops"))
        self.jobs = int(Params.get(self.module, "jobs"))
        self.toolchain = Params.get(self.module, "toolchain")
        if self.loops < 1 or not 0 <= self.jobs <= 4096:
            raise ValueError("loops must be positive; jobs must be between 0 and 4096.")
        self._measurement_attempted = False
        self._failed = False
        self._teardown_done = False
        self._ready = False
        self.addCleanup(self.tearDown)
        try:
            prep_command = self.command("prep")
            destination = ntpath.join(self.dut_exec_path, self.resources)
            self._remote_make_dir(f'"{destination}"')
            # Preserve the prep-installed Python environment on repeated uploads.
            for name in ("build.py", "invoke.ps1", self.workload + ".json"):
                self._upload(str(Path(__file__).parent / self.resources / name), destination, check_modified=False)
            # Prep is idempotent and verifies artifacts, not just HOBL's status marker.
            self._call(prep_command, timeout=3600)
            self._ready = True
            self.createPrepStatusControlFile(self.prep_version)
            self._measurement_attempted = True
            super().setUp()
        except BaseException:
            self._failed = True
            raise

    def runTest(self):
        try:
            for sample in range(1, self.loops + 1):
                self._call(self.command("run", sample), timeout=2700)
        except BaseException:
            self._failed = True
            raise

    def tearDown(self):
        if self._teardown_done:
            return
        self._teardown_done = True
        errors = []
        if self._measurement_attempted:
            try:
                super().tearDown()
            except Exception as error:
                logging.exception("Failed to stop Rust workload measurement.")
                errors.append(error)
        if self._ready:
            try:
                self._call(self.command("teardown"), timeout=300)
            except Exception as error:
                logging.exception("Failed to clean owned Rust build outputs.")
                errors.append(error)
        try:
            self._copy_data_from_remote(self.result_dir)
        except Exception as error:
            logging.exception("Failed to collect Rust workload diagnostics.")
            errors.append(error)
        if errors and not self._failed:
            raise errors[0]

    def kill(self):
        try:
            self.platform = Params.get("global", "platform")
            self.jobs = int(Params.get(self.module, "jobs"))
            self.toolchain = Params.get(self.module, "toolchain")
            self._call(self.command("kill"), timeout=60)
        except Exception:
            logging.exception("Failed to request cancellation of this Rust workload.")
        return 0
