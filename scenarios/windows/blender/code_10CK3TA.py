# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import time

def run(scenario):
    logging.debug('Executing code block: code_10CK3TA.py')
    logging.debug('Checking if benchmark-launcher-cli.exe is already on the DUT')

    # Define paths
    zip_file = os.path.join("scenarios", "blender_resources", "benchmark-launcher-cli.zip")
    extract_dir = os.path.join("scenarios", "blender_resources", "windows")
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
    exe_file = os.path.join(extract_dir, "benchmark-launcher-cli.exe")

    # Download the zip file if not already present
    scenario._check_and_download('benchmark-launcher-cli.zip', "scenarios\\blender_resources", url='https://download.blender.org/release/BlenderBenchmark2.0/launcher/benchmark-launcher-cli-3.3.0-windows.zip')
    
    try:
        # Extract the zip file
        scenario._host_call(["cmd.exe", "/C " + f"tar -xf {zip_file} -C {extract_dir}"], expected_exit_code="")
    except:
        logging.debug("Could already being extracted, wait for extraction to finish")
        time.sleep(5)

    # Check if the .exe file already exists on the DUT
    if scenario._check_remote_file_exists(os.path.join(scenario.dut_exec_path, "benchmark-launcher-cli.exe"), False):
        logging.info("benchmark-launcher-cli.exe already found on DUT. Skipping upload")
    else:
        logging.info("Uploading benchmark-launcher-cli.exe to " + scenario.dut_exec_path)
        scenario._upload(exe_file, scenario.dut_exec_path)
    
    logging.info("Checking/Downloading Benchmark Version")
    scenario._call(["cmd.exe", "/C " + os.path.join(scenario.dut_exec_path, "benchmark-launcher-cli.exe") + " blender download 5.1.1"], expected_exit_code="")
    
    logging.info("Checking/Downloading Benchmark Scenes")
    scenario._call(["cmd.exe", "/C " + os.path.join(scenario.dut_exec_path, "benchmark-launcher-cli.exe") + " scenes download --blender-version 5.1.1 monster junkshop classroom"], expected_exit_code="")

