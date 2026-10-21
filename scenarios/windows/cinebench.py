# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import re
from core.parameters import Params
import core.app_scenario

class Cinebench(core.app_scenario.Scenario):
    """
    The Cinebench benchmark.
    """
    module = __module__.split('.')[-1]
    is_benchmark = True

    Params.setDefault(module, 'duration', '60', desc="Minimum run time in seconds")
    Params.setDefault(module, 'workload', 'multi_core', desc="Workload type: single_core or multi_core", valOptions=["single_core", "multi_core"])
    Params.setDefault(module, 'installer_path', '', desc="Path to Cinebench installer on host machine. This should be the directory for your device architecture, containing the extracted Cinebench files, including cinebench.exe")
    prep_version = "1"

    prep_run_only = Params.get('global', 'prep_run_only') == "1"

    def setUp(self):
        self.toolCallBacks("testBeginEarlyCallback")
        
        self.duration = int(Params.get(self.module, 'duration'))
        self.workload = Params.get(self.module, 'workload')
        self.dut_arch = Params.get('global', 'dut_architecture')

        self.installer_path = Params.get(self.module, 'installer_path')

        # Get the name of the folder that was uploaded to the device, which should be the same as the last part of the installer path
        self.folder_name = self.installer_path.split('\\')[-1]
        
        self.cinebench_path = f"{self.dut_exec_path}\\Cinebench\\{self.folder_name}\\cinebench.exe"
        self.out_filename = "cinebench_output.txt"

        self.prep()

        super().setUp()

    def prep(self):
        prep_suffix = f"_{self.folder_name}_{self.prep_version}"

        if self.checkPrepStatus([self.module + prep_suffix]):
            self._upload(f"{self.installer_path}", f"{self.dut_exec_path}\\Cinebench")
            self.createPrepStatusControlFile(prep_suffix)

    def runTest(self):
        if self.workload == 'single_core':
            workload_arg = 'g_CinebenchCpu1Test=true'
        else:
            workload_arg = 'g_CinebenchCpuXTest=true'
        logging.info("Cinebench started.")
        self._call(["cmd.exe", f'/c start /B /wait "parent" {self.cinebench_path} {workload_arg} g_CinebenchMinimumTestDuration={self.duration} > {self.dut_data_path}\\{self.out_filename}"'], timeout=self.duration + 2700)
        logging.info("Cinebench completed.")

    def parse_values(self, s):
        match = re.search(
            r"Values:\s*\{([^}]*)\}\s*->\s*Avg/Deviation:\s*([\d.]+)/([\d.]+)",
            s
        )

        if not match:
            raise ValueError("Invalid input format")

        values = [float(x) for x in match.group(1).split(",")]
        avg    = float(match.group(2))
        std    = float(match.group(3))

        return (values, avg, std)

    def tearDown(self):
        if self.prep_run_only:
            return

        logging.info("Tearing down Cinebench scenario.")
        # Baseclass test end callback to stop tools
        self._callback(Params.get('global', 'callback_test_end'))

        # Download output file
        self._copy_data_from_remote(dest = self.result_dir, source = self.dut_data_path + '\\' + self.out_filename, single_file=True)

        # Extract score from output file
        output_file = os.path.join(self.result_dir, self.out_filename)
        logging.info(f"Extracting score from {output_file}")
        values = None
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("Values:"):
                    try:
                        values = self.parse_values(line.strip())
                    except:
                        logging.debug(f"Failed to parse CB values: {line.strip()}")
                if line.strip().startswith("CB "):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            score = float(parts[1])
                        except ValueError:
                            logging.error(f"Failed to convert score to float: {parts[1]}")

        # Write score to cinebench.csv
        with open(self.result_dir + '\\cinebench.csv', 'w') as out:
            if values:
                for i, value in enumerate(values[0]):
                    out.write(f"Cinebench Render {i+1} Score,{value}\n")

                out.write(f"Cinebench Avg Score,{values[1]}\n")
                out.write(f"Cinebench Std Score,{values[2]}\n")

            if self.workload == 'single_core':
                out.write(f"Cinebench Single Core Score,{score}\n")
            else:
                out.write(f"Cinebench Multi Core Score,{score}\n")

        super().tearDown(callback_test_end="")

        if self.workload == 'single_core':
            logging.info(f"Cinebench Single Core Score: {score}")
        else:
            logging.info(f"Cinebench Multi Core Score: {score}")

    def kill(self):
        # In case of scenario failure or termination, kill any applications left open here:
        try:
            self._kill("cinebench.exe")
        except:
            pass
        return
