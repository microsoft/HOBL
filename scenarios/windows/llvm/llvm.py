# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# LLVM Build Workload
##

import base64
import hashlib
import logging
import os
import re
import scenarios.app_scenario
from parameters import Params
from datetime import datetime

class Llvm(scenarios.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "10"
    resources = module + "_resources"


    # Set default parameters
    Params.setDefault(module, 'loops', '1')
    Params.setDefault(module, 'installer_path', '', desc="Optional host-side LLVM MSI path; never committed or downloaded implicitly.")
    Params.setDefault(module, 'installer_sha256', '', desc="Required approved SHA-256 when installer_path is set.")
    Params.setDefault(module, 'compiler_version', '', desc="Required MSI/compiler version (major.minor.patch) when installer_path is set; source tag is unchanged.")
    Params.setDefault(module, 'allow_unsigned_installer', '0', desc="Explicitly trust the hash-pinned unsigned MSI; does not bypass Windows policy.", valOptions=['0', '1'])

    @staticmethod
    def _powershell_command(script, **parameters):
        # RPC accepts an executable and one argument string. Encode the command
        # so spaces/metacharacters in paths cannot become PowerShell code.
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = "& " + quote(script)
        for name, value in parameters.items():
            if isinstance(value, bool):
                if value:
                    command += f" -{name}"
            else:
                command += f" -{name} {quote(value)}"
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return ['pwsh', f'-NoProfile -NonInteractive -EncodedCommand {encoded}']


    def setUp(self):
        # Get parameters
        self.platform = Params.get('global', 'platform')
        self.loops = Params.get(self.module, 'loops')

        self.target = f"{self.dut_exec_path}\\{self.resources}"

        installer = Params.get(self.module, 'installer_path').strip()
        self.installer_sha256 = Params.get(self.module, 'installer_sha256').strip().lower()
        self.compiler_version = Params.get(self.module, 'compiler_version').strip()
        allow_unsigned = Params.get(self.module, 'allow_unsigned_installer') == '1'
        if installer:
            if not re.fullmatch(r'[0-9a-f]{64}', self.installer_sha256):
                raise ValueError('llvm:installer_sha256 must be the approved 64-character SHA-256.')
            if not re.fullmatch(r'\d+\.\d+\.\d+', self.compiler_version):
                raise ValueError('llvm:compiler_version must be major.minor.patch.')
            if os.path.splitext(installer)[1].lower() != '.msi':
                raise ValueError('llvm:installer_path must refer to an MSI.')
            selection = f'msi_{self.compiler_version}_{self.installer_sha256}'
        else:
            if self.installer_sha256 or self.compiler_version or allow_unsigned:
                raise ValueError('LLVM MSI options require llvm:installer_path.')
            self.compiler_version = '21.1.8'
            selection = 'default'

        # Resource upload replaces the resource directory. Only the current
        # toolchain selection gets a marker, so A -> B -> A also re-preps.
        selection_marker = f'{self.resources}\\compiler_{selection}'
        needs_prep = bool(self.checkPrepStatus([self.module + self.prep_version]))
        if not needs_prep and self.prep_status_enable:
            needs_prep = not self._check_remote_file_exists(selection_marker)

        # Test if already set up
        if needs_prep:
            logging.info("Preparing for first use.")

            if installer:
                if not os.path.isfile(installer):
                    raise FileNotFoundError('LLVM MSI is not accessible to the HOBL host account. Use an accessible local or UNC path.')
                digest = hashlib.sha256()
                with open(installer, 'rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                if digest.hexdigest() != self.installer_sha256:
                    raise ValueError('LLVM MSI SHA-256 does not match the approved value; nothing uploaded.')

            # Copy over resources to DUT
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}", self.dut_exec_path)

            prep_parameters = {}
            if installer:
                # Force transfer: timestamps are not an integrity check.
                self._upload(installer, self.target, check_modified=False)
                prep_parameters = dict(
                    InstallerPath=f'{self.target}\\{os.path.basename(installer)}',
                    InstallerSha256=self.installer_sha256,
                    CompilerVersion=self.compiler_version,
                    AllowUnsignedInstaller=allow_unsigned,
                )

            # Execute prep script
            logging.info("Executing prep, this may take 30-60 minutes...")
            try:
                self._call(self._powershell_command(f"{self.target}\\{self.module}_prep.ps1", **prep_parameters), timeout=3600)
            finally:
                self._copy_data_from_remote(self.result_dir)
            self._remote_make_dir(f'{self.dut_exec_path}\\{selection_marker}')
            if not self._check_remote_file_exists(selection_marker):
                raise RuntimeError('LLVM compiler selection marker could not be created; prep is incomplete.')
            self.createPrepStatusControlFile(self.prep_version)

        # Call base class setUp() to dump config, call tool callbacks, and start measurement
        scenarios.app_scenario.Scenario.setUp(self)


    def runTest(self):
        start_time = datetime.now().astimezone().isoformat()
        for i in range(int(self.loops)):
            logging.info(f"Running loop {i + 1}")
            # Disable fail_on_exception because ninja build output includes LLVM source
            # filenames containing "Exception" (e.g., exception handling code), which
            # triggers a false positive in _call's output scanning.
            self._call(self._powershell_command(
                f"{self.target}\\{self.module}_run.ps1", startTime=start_time,
                CompilerVersion=self.compiler_version, InstallerSha256=self.installer_sha256,
            ), fail_on_exception=False)


    def tearDown(self):
        logging.info("Performing teardown.")
        # Call base class tearDown() to stop measurement, copy back data from DUT, and call tool callbacks
        scenarios.app_scenario.Scenario.tearDown(self)


    def kill(self):
        try:
            logging.debug("Killing powershell shell")
            self._kill("pwsh.exe")
        except:
            pass
