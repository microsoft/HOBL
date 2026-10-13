# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Intel Battery Life Diagnostic Tool System Configuration Checker scenario."""

import base64
import logging

import core.app_scenario
from core.parameters import Params


class BldtSysconfig(core.app_scenario.Scenario):

    is_prep = True
    module = __module__.split('.')[-1]
    prep_version = "1"
    resources = module + "_resources"
    prep_marker_module = "bldt"

    Params.setDefault(module, 'loops', '1')
    Params.setDefault(
        module,
        'use_ai',
        'false',
        desc='Install/require the BLDT AI edition. The AI edition also satisfies standard requests.',
        valOptions=['true', 'false'],
    )
    Params.setDefault(
        module,
        'power_source',
        'AC',
        desc='Power source passed to BLDT SysConfigChecks.',
        valOptions=['AC', 'DC'],
    )

    @staticmethod
    def _powershell_command(script, **parameters):
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = "& " + quote(script)
        for name, value in parameters.items():
            command += f" -{name} {quote(value)}"
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return ['powershell.exe', f'-NoProfile -NonInteractive -EncodedCommand {encoded}']

    def _prep_command(self, validate_only=False):
        parameters = {
            'UseAi': str(self.use_ai).lower(),
            'LogFile': f"{self.dut_data_path}\\bldt_sysconfig_prep.log",
        }
        if validate_only:
            parameters['ValidateOnly'] = 'true'
        return self._powershell_command(
            f"{self.target}\\bldt_sysconfig_prep.ps1",
            **parameters,
        )

    def _run_prep(self):
        if self.use_ai:
            logging.info("Preparing Intel BLDT v3.1.1 AI edition; the AI package may take over an hour to download and extract.")
        else:
            logging.info("Preparing Intel BLDT v3.1.1 standard edition.")
        try:
            self._call(self._prep_command(), timeout=10800)
            self._call(self._prep_command(validate_only=True), timeout=300)
        finally:
            self._copy_data_from_remote(self.result_dir)
        self.createPrepStatusControlFile(self.prep_version, module=self.prep_marker_module)

    def setUp(self):
        self.loops = int(Params.get(self.module, 'loops'))
        if self.loops < 1:
            raise ValueError('bldt_sysconfig:loops must be at least 1.')

        use_ai = Params.get(self.module, 'use_ai').strip().lower()
        if use_ai not in ('true', 'false'):
            raise ValueError('bldt_sysconfig:use_ai must be true or false.')
        self.use_ai = use_ai == 'true'

        self.power_source = Params.get(self.module, 'power_source').strip().upper()
        if self.power_source not in ('AC', 'DC'):
            raise ValueError('bldt_sysconfig:power_source must be AC or DC.')

        self.target = f"{self.dut_exec_path}\\{self.resources}"
        logging.info("Uploading BLDT scenario resources to %s", self.target)
        self._upload(
            f"scenarios\\windows\\{self.module}\\{self.resources}",
            self.dut_exec_path,
        )
        needs_prep = bool(self.checkPrepStatus([self.prep_marker_module + self.prep_version]))

        if not needs_prep:
            try:
                self._call(self._prep_command(validate_only=True), timeout=300)
            except Exception as error:
                logging.warning("BLDT live validation failed; prep will repair the installation: %s", error)
                needs_prep = True

        if needs_prep:
            self._run_prep()

        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        for loop_index in range(self.loops):
            logging.info("Running BLDT SysConfigChecks loop %d of %d", loop_index + 1, self.loops)
            self._call(
                self._powershell_command(
                    f"{self.target}\\bldt_sysconfig_run.ps1",
                    UseAi=str(self.use_ai).lower(),
                    PowerSource=self.power_source,
                    LoopNumber=loop_index + 1,
                ),
                timeout=1800,
            )

    def tearDown(self):
        logging.info("Collecting BLDT SysConfigChecks logs, metrics, and reports.")
        core.app_scenario.Scenario.tearDown(self)

    def kill(self):
        for process_name in ('BatteryLifeDiagnosticTool.exe', 'bldtUI.exe'):
            try:
                self._kill(process_name)
            except Exception:
                logging.debug("BLDT process was not running: %s", process_name)
