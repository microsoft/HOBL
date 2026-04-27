# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_10V9XFL.py')
    benchmark_option = Params.get('blender', 'benchmark_option')
    scenario._call([f"cmd.exe", "/C " + os.path.join(scenario.dut_exec_path, "benchmark-launcher-cli.exe") + " benchmark --blender-version 5.1.1 --device-type " + benchmark_option + " --json monster junkshop classroom > C:\\hobl_data\\blender_result.txt 2>&1"], expected_exit_code="")
