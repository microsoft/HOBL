# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# PyTorch Inferencing Workload v2 -- GPU-first Qwen3 LLM benchmark
# (replacement for pytorch_inf; see README.md for the full design rationale)
##

import logging
import core.app_scenario
from core.parameters import Params
from datetime import datetime

class PytorchInfV2(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "1"
    resources = module + "_resources"

    # Set default parameters
    Params.setDefault(module, 'loops', '2')
    Params.setDefault(module, 'use_gpu', 'true', valOptions=["true", "false"])
    Params.setDefault(module, 'model_tier', 'portable', valOptions=["portable", "quantized"])
    Params.setDefault(module, 'lane', 'eager', valOptions=["eager", "compiled"])
    Params.setDefault(module, 'quant', 'none', valOptions=["none", "int4", "nvfp4"])
    Params.setDefault(module, 'shape', 'short', valOptions=["short", "long", "sustained"])


    def setUp(self):
        # Get parameters
        self.platform = Params.get('global', 'platform')
        self.loops = Params.get(self.module, 'loops')
        self.use_gpu = Params.get(self.module, 'use_gpu').lower() == 'true'
        self.model_tier = Params.get(self.module, 'model_tier')
        self.lane = Params.get(self.module, 'lane')
        self.quant = Params.get(self.module, 'quant')
        self.shape = Params.get(self.module, 'shape')

        self.target = f"{self.dut_exec_path}\\{self.resources}"

        self.prep()

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def prep(self):
        # Test if already set up
        if not self.checkPrepStatusNew([(self.module, self.prep_version)]):
            return

        logging.info("Preparing for first use.")

        # Copy over resources to DUT
        logging.info(f"Uploading test files to {self.target}")
        self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}", self.dut_exec_path)

        # Execute prep script. GPU-first setup: installs pyenv Python 3.14.8,
        # a per-scenario venv, the pinned PyTorch/transformers/torchao stack
        # (verified-hash NVIDIA wheel on Arm64), and pre-downloads both model
        # tiers outside of scored time.
        logging.info("Executing prep, this may take 10-15 minutes...")
        if self.platform.lower() == "macos":
            try:
                self._call(["zsh", f"{self.target}/{self.module}_prep.sh"])
            finally:
                self._copy_data_from_remote(self.result_dir)
        else:
            prep_cmd = f"{self.target}\\{self.module}_prep.ps1"
            try:
                self._call(["pwsh", prep_cmd])
            finally:
                self._copy_data_from_remote(self.result_dir)
        self.createPrepStatusControlFile(self.prep_version)


    def runTest(self):
        start_time = datetime.now().astimezone().isoformat()
        for i in range(int(self.loops)):
            logging.info(f"Running loop {i + 1}")
            run_cmd = (
                f"{self.target}\\{self.module}_run.ps1 -startTime {start_time}"
                f" -modelTier {self.model_tier} -lane {self.lane} -quant {self.quant} -shape {self.shape}"
            )
            if not self.use_gpu:
                run_cmd += " -noGpu"
            self._call(["pwsh", run_cmd])


    def tearDown(self):
        logging.info("Performing teardown.")
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        logging.info("Executing teardown script.")
        self._call(["pwsh", f"{self.target}\\{self.module}_teardown.ps1"])


    def kill(self):
        try:
            logging.debug("Killing python process")
            self._kill("python.exe")
        except:
            pass
