# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

import core.app_scenario
from core.parameters import Params


class MacFastApiApp(core.app_scenario.Scenario):

    module = __module__.split(".")[-1]
    prep_version = "1"
    resources = module + "_resources"

    Params.setDefault(module, "loops", "5")
    Params.setDefault(
        module,
        "reload_mode",
        "none",
        desc="Reload measurement mode",
        valOptions=["none", "managed", "external"],
    )
    Params.setDefault(module, "reload_port", "8765")

    def setUp(self):
        self.loops = Params.get(self.module, "loops")
        self.reload_mode = Params.get(self.module, "reload_mode")
        self.reload_port = Params.get(self.module, "reload_port")
        self.target = f"{self.dut_exec_path}/{self.resources}"
        prep_required = self.checkPrepStatus(
            [self.module + self.prep_version]
        )
        if self.reload_mode == "external" and prep_required:
            raise RuntimeError(
                "Run mac_fast_api_app once with reload_mode=none before "
                "using the external foreground reload mode."
            )

        self._upload(
            f"scenarios\\macos\\{self.module}\\{self.resources}",
            self.dut_exec_path,
        )
        if self.reload_mode != "external":
            self._upload(
                "scenarios\\common\\fast_api_app_workload",
                self.dut_exec_path,
            )

        if prep_required:
            logging.info("Preparing FastAPI application workload.")
            try:
                self._call(
                    ["zsh", f"{self.target}/{self.module}_prep.sh"],
                    timeout=3600,
                )
            finally:
                self._copy_data_from_remote(self.result_dir)
            self.createPrepStatusControlFile(self.prep_version)

        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        self._call(
            [
                "zsh",
                (
                    f"{self.target}/{self.module}_run.sh "
                    f"{self.loops} {self.reload_mode} {self.reload_port}"
                ),
            ],
            timeout=3600,
        )

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)

    def kill(self):
        return
