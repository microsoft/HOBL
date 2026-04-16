# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from cmath import log
from datetime import datetime
from builtins import str
from builtins import *
import math
import unittest
import logging
import subprocess
import traceback
from appium import webdriver
from core.parameters import Params, reg_read, reg_write, reg_clean
import os
import os.path
import stat
import shutil
import core.call_rpc as rpc
import socket
import select
import importlib
import json
import io
import glob
import random
import requests
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common import utils as common_utils
from selenium.webdriver.remote.remote_connection import RemoteConnection
import threading
import time
import ctypes
import csv
from contextlib import closing
from queue import Queue, Empty
import sys
import tempfile
import cv2 as cv
import numpy as np
import qoi
import imutils
from PIL import Image
from urllib.parse import (
    urlparse,
    urlunparse
)
import zipfile
import re
import copy
from datetime import datetime
from pathlib import Path

# Base class for each application test scenario

sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

class Scenario(unittest.TestCase):
    is_prep = False
    ffmpeg_launched = False
    toolCallBacks_failed = False
    toolCallBacks_backtrace = []
    tool_failure_reason = None

    web_replay_version = "v1.5.0"
    MAX_SCREENS = 4  # Maximum number of screens to support

    def __init__(self, *args, **kwargs):
        # lock object for adb syncronization
        self.adbLock = threading.Lock()
        self.daq_start_time = 0
        self.daq_prev_time = 0
        self.daq_accumulated_time = 0
        self.scenario_start_time = time.time()
        self.scenario_prev_time = self.scenario_start_time
        self.scenario_accumulated_time = 0
        self.log_scenario_events = False
        self.counter = 0
        self.enable_screenshot = '0'
        self.enable_tool_threading = False
        self.timeout_wake = '0'
        self.trace_started = False
        self.drivers = []
        self.activeHostCalls = []
        self.dut_conn_timeout = False
        self._module = self.__module__.split('.')[-1]
        self.bare = False
        self.component = None
        self.current_screen = 0

        # Reset tooCallback values on each attempt
        self.reset_toolCallBacks_result()

        #variables added for tools
        self.enable_strategic_screenshot = '0'
        self.video_startTime = None
        self.inputInject_startTime = {}

        # Get key paramaters before tool initialization
        self.dut_alive = Params.getCalculated("dut_alive")
        self.dut_ip = Params.get('global', 'dut_ip')
        self.host_ip = Params.get('global', 'host_ip')
        self.result_dir = Params.getCalculated("run_dir")
        self.testname = Params.getCalculated("test_name")
        self.platform = Params.get('global', 'platform')
        self.app_port = Params.get('global', 'app_port')
        self.rpc_port = 8000  # TODO: move to parameter?
        self.rpc_callback_port = 8010  # TODO: move to parameter?
        self.web_port = Params.get('global', 'web_port')
        self.async_comm = Params.get('global', 'async_comm')
        self.password = Params.get('global', 'dut_password')
        self.training_mode = Params.get('global', 'training_mode')
        self.typing_delay = Params.get('global', 'typing_delay')
        self.dut_scaling_override = Params.get('global', 'dut_scaling_override')
        self.dut_coord_scaler = float(Params.get('global', 'dut_coord_scaler'))
        self.dashboard_url = Params.get('global', 'dashboard_url')

        self.web_replay_run = Params.get('global', 'web_replay_run')
        self.web_replay_action = Params.get('global', 'web_replay_action')
        self.web_replay_recording = Params.get('global', 'web_replay_recording')
        self.web_replay_rand_ports = Params.get('global', 'web_replay_rand_ports')
        self.web_replay_http_port = Params.get('global', 'web_replay_http_port')
        self.web_replay_https_port = Params.get('global', 'web_replay_https_port')
        self.web_replay_http_proxy_port = Params.get('global', 'web_replay_http_proxy_port')
        self.web_replay_excludes_list = Params.get('global', 'web_replay_excludes_list')
        self.web_replay_ip = Params.get('global', 'web_replay_ip')

        # Output full hobl command to log file
        logging.debug("Hobl Command: " + " ".join(sys.argv))

        if self.platform.lower() == "macos":
            # On MacOS, 300ms tends to be a long press, so we reduce the default click time.
            self.default_click_time = 150  # milliseconds
        else:
            self.default_click_time = 300  # milliseconds

        if self.web_replay_ip == "":
            self.web_replay_ip = self.host_ip

        self.browser = Params.get('global', 'browser')

        # bare argument prevents tools from being initialized and hobl directories recreated (used in action_list).
        if "bare" in kwargs:
            self.bare = kwargs["bare"]

        if self.bare:
            return

        logging.debug("ORDER app_scenario __init__ for: " + self._module)

        if "is_tool" in kwargs:
            self.is_tool = kwargs["is_tool"]
        else:
            self.is_tool = False
        if self.is_tool:
            logging.debug("Initializing tool " + self._module)

        if "is_prep_tool" in kwargs:
            self.is_prep_tool = kwargs["is_prep_tool"]
        else:
            self.is_prep_tool = False
        if self.is_prep_tool:
            logging.debug("Initializing prep_tool " + self._module)

        # Resolve IP
        if self.is_tool or self.is_prep_tool:
            # If this is a tool, we will use the resolved IP from the scenario, stored in the Params object.
            self.dut_resolved_ip = Params.getCalculated("dut_resolved_ip")
            logging.debug(f"Using previously resolved IP: {self.dut_resolved_ip}")

        elif self.dut_alive == '1':
            # If there are any letters in dut_ip, then it is a name and we can get the real numeric IP.  Numberic IP is only needed for launching webdriver.
            if self.dut_ip.upper().isupper():
                logging.debug(f"Resolving IP for: {self.dut_ip}")
                resolve_attempt = 0
                while resolve_attempt < 3:
                    try:
                        # Try to resolve the IP using the socket library
                        try:
                            self.dut_resolved_ip = socket.gethostbyname(self.dut_ip)
                            if self.dut_resolved_ip is None:
                                raise Exception(f"Could not resolve IP for {self.dut_ip} with Python socket library")
                            
                        # If we can't resolve the IP, we will try to resolve using the common_utils library
                        except:
                            self.dut_resolved_ip = common_utils.find_connectable_ip(self.dut_ip)
                            if self.dut_resolved_ip is None:
                                raise Exception(f"Could not resolve IP for {self.dut_ip} with Selenium common_utils library")
                        
                        # If we got an IP, we can break out of the loop
                        break

                    # If we can't resolve the IP, we will retry up to 3 times
                    except:
                        resolve_attempt += 1 # Increment the attempt counter
                        logging.warning(f"Attempt {resolve_attempt} Could not resolve IP for: {self.dut_ip}")
                        exp_backoff = 2 ** resolve_attempt # Exponential backoff 1 to 4 seconds
                        logging.warning(f"Waiting {exp_backoff} seconds before retrying.")
                        time.sleep(exp_backoff) # Wait before retrying
                        pass

                # If we still can't resolve the IP after 3 attempts, we will raise an exception
                if resolve_attempt >= 3:
                    logging.error(f"Could not resolve IP for: {self.dut_ip}")
                    raise Exception(f"Could not resolve IP for: {self.dut_ip}")

                logging.debug(f"Resolved to IP: {self.dut_resolved_ip}")
            else:
                logging.debug(f"IP is already numeric: {self.dut_ip}")
                self.dut_resolved_ip = self.dut_ip
                logging.debug(f"Using IP: {self.dut_resolved_ip}")
            
            # Store the resolved IP in the Params object
            Params.setCalculated("dut_resolved_ip", self.dut_resolved_ip)

        # Checking for local execution and running from web ui. If so then we want to kill web ui.
        if self.dut_ip == "127.0.0.1" and self.dashboard_url != '':
            self._kill("msedge.exe")
            
        # Set up dut_exec_path and dut_data_path.  Doing it before tools initialized in case they need it.
        if Params.get('global', 'local_execution') == '1':
            self.dut_exec_path = "C:\\hobl_bin"
            self.dut_data_path = self.result_dir

        else:
            if self.platform.lower() == 'wcos':
                self.dut_exec_path = "C:\\Data\\test\\bin\\hobl_bin"
                self.dut_data_path = "C:\\Data\\test\\bin\\hobl_data"
            elif self.platform.lower() == 'macos':
                self.dut_exec_path = "/Users/Shared/hobl_bin"
                self.dut_data_path = "/Users/Shared/hobl_data"
            else:
                self.dut_exec_path = "C:\\hobl_bin"
                self.dut_data_path = "C:\\hobl_data"

        if self.platform.lower() == "android":
            self.dut_exec_path = "/sdcard/hobl_bin"
            self.dut_data_path = "/sdcard/hobl_data"

        Params.setCalculated("dut_exec_path", self.dut_exec_path)
        Params.setCalculated("dut_data_path", self.dut_data_path)

        self.dut_exec_path = Params.getCalculated("dut_exec_path")
        # Fix for local execution allows config's to copy to correct path
        if Params.get('global', 'local_execution') == '0':
            self.dut_data_path = Params.getCalculated("dut_data_path")

        self.roots = [
            Path.cwd(),
            *[Path(p) for p in Params.get('global', 'hobl_external').split()]
        ]

        self.prep_status_enable = Params.get('global', 'prep_status_enable') == "1"
        self.prep_run_only      = Params.get('global', 'prep_run_only') == "1"
        if self.prep_run_only: self.is_prep = True

        if not (self.is_prep or self.is_tool or self.is_prep_tool) and self.prep_status_enable:
            prep_scenarios_to_run = self.checkPrepStatusNew(getattr(self, 'prep_scenarios', []))
            Params.setCalculated("prep_scenarios_to_run", prep_scenarios_to_run)

        if self.is_tool == False and self.is_prep_tool == False and self.dut_alive == '1':
            # Check DUT Setup version
            if self.platform.lower() == 'windows':
                # Read first line of setup/src_dut_win/dut_setup.cmd
                with open("setup_src/src_dut_win/dut_setup.cmd", "r") as f:
                    lines = f.readlines()
                    if lines:
                        first_line = lines[0].strip()
                        logging.debug(f"DUT Setup first line: {first_line}")
                        if first_line.startswith("set dut_setup_version="):
                            expected_dut_setup_version = first_line.split('=')[1].strip()
                            expected_dut_setup_major_version = expected_dut_setup_version.split('.')[0]
                            expected_dut_setup_minor_version = expected_dut_setup_version.split('.')[1]
                            logging.debug(f"Expected DUT Setup version: {expected_dut_setup_major_version}.{expected_dut_setup_minor_version}")
                # Read last line of dut_setup.log on DUT to get actual DUT setup version
                try:
                    last_line = self._call(["powershell", "-Command Get-Content -Path 'C:\\hobl_bin\\dut_setup.log' | Select-Object -Last 1"], expected_exit_code="", fail_on_exception=False)
                    if last_line.startswith("dut_setup version: "):
                        actual_dut_setup_version = last_line.split(': ')[1].strip()
                        actual_dut_setup_major_version = actual_dut_setup_version.split('.')[0]
                        actual_dut_setup_minor_version = actual_dut_setup_version.split('.')[1]
                        logging.debug(f"Actual DUT Setup version: {actual_dut_setup_major_version}.{actual_dut_setup_minor_version}")
                        if actual_dut_setup_major_version != expected_dut_setup_major_version:
                            logging.error(f"DUT Setup version {actual_dut_setup_version} does not match required version {expected_dut_setup_version}. You need to run the latest dut_setup.exe on the DUT.")
                        elif actual_dut_setup_minor_version != expected_dut_setup_minor_version:
                            logging.warning(f"DUT Setup version {actual_dut_setup_version} does not match expected version {expected_dut_setup_version}. It is recommended to re-run the latest dut_setup.exe on the DUT.")
                    else:
                        logging.warning("Could not determine actual DUT Setup version.")
                except:
                    logging.warning("Could not read dut_setup.log on DUT to determine actual DUT Setup version.")
                    pass
            # Load InputInject plugin to SimpleRemote
            if self.platform.lower() == 'macos':
                result = rpc.plugin_load(self.dut_ip, self.rpc_port, "InputInject", "InputInject.Application", "/Users/Shared/hobl_bin/InputInject/InputInject.dll")
            else:
                result = rpc.plugin_load(self.dut_ip, self.rpc_port, "InputInject", "InputInject.Application", "C:\\hobl_bin\\InputInject\\InputInject.dll")

            if Params.get('global', 'local_execution') == '0':
                # Create and/or delete contents of hobl_data
                logging.debug("ORDER app_scenario creating DUT folders: " + self._module)
                if self.platform.lower() == "windows":
                    source_path = "C:\\simple_remote_*.log"
                    try:
                        self._call(["cmd.exe", '/c del ' + source_path], expected_exit_code="", timeout = 10)
                    except:
                        logging.warning("Could not delete simple_remote log.")
                        pass

                # Don't delete data at the end, in case we need to manually retrieve it.
                if Params.getCalculated("kill_mode") != "1":
                    self._remote_make_dir(self.dut_data_path, True)
                else:
                    self._remote_make_dir(self.dut_data_path, False)
                    
                self._remote_make_dir(self.dut_exec_path, False)
                # TODO: detect failure of make_dir
                # TODO: Tools are trying to create dut_data_path as well, need to prevent reattempts, but tool may be first.
            else:
                # if it is local execution we should do a host call and mkdir ?
                self._remote_make_dir(self.dut_exec_path, False)


            if self.platform.lower() == "windows":
                try:
                    if Params.get("global", "local_execution") == "0":
                        self.userprofile = self._call(["cmd.exe", "/C echo %USERPROFILE%"])
                    else:
                        self.userprofile = os.environ['USERPROFILE']
                    Params.setParam('global', 'userprofile', self.userprofile)
                except:
                    self.userprofile = "C:\\Users\\Default"
                    Params.setParam('global', 'userprofile', self.userprofile)

        if self.is_tool == False and self.is_prep_tool == False:
            # Only call unittest constructor if this is not a tool.
            # logging.debug("ORDER app_scenario calling scenario __init__: " + self._module)
            super(Scenario, self).__init__(methodName='runScenario')

        self.tools = Params.get('global', 'tools')
        self.prep_tools = Params.get('global', 'prep_tools')

        # Initialize tools
        self.tool_instances = []
        if self.is_tool == False and self.is_prep_tool == False and self.is_prep == False:
            for tool in dict.fromkeys(self.tools.split()):
                logging.debug("ORDER app_scenario initializing tool: " + tool)
                try:
                    tool_module = importlib.import_module("tools." + tool)
                    tool_class = getattr(tool_module, "Tool")
                    tool_instance = tool_class(is_tool=True, scenario=self)
                    self.tool_instances.append(tool_instance)
                except:
                    self.tool_failure_reason = f"Tool \"{tool}\" not found. Possibly check the spelling?"

        self.prep_tool_instances = []
        if self.is_prep_tool == False and self.is_tool == False and self.is_prep == True:
            for prep_tool in dict.fromkeys(self.prep_tools.split()):
                logging.debug(
                    "ORDER app_scenario initializing prep_tool: " + prep_tool)
                try:
                    prep_tool_module = importlib.import_module(
                        "tools." + prep_tool)
                    prep_tool_class = getattr(prep_tool_module, "Tool")
                    prep_tool_instance = prep_tool_class(
                        is_prep_tool=True, scenario=self)
                    self.tool_instances.append(prep_tool_instance)
                except:
                    self.tool_failure_reason = f"Prep tool \"{prep_tool}\" not found. Possibly check the spelling?"

        # cleanup will be called after teardown or if setup fails, by the Python Unit Test framework.
        # if self.is_tool == False and self.is_prep == False and self.is_prep_tool == False:
        if self.is_tool == False and self.is_prep_tool == False:
            # This needs to be one in __init__() because tools can do testBeginEarlyCallback, which happens before setup.
            def cleanup():
                logging.debug("Cleaning up tools")
                self.toolCallBacks("cleanup")
            self.addCleanup(cleanup)

        # Get these key paramaters after tool initialization
        self.collection_enabled = Params.get('global', 'collection_enabled')
        self.stop_soc = Params.get('global', 'stop_soc')
        self.crit_batt_level = Params.get('global', 'crit_batt_level')
        self.trigger_soc = Params.get('global', 'trigger_soc')
        self.trigger_script = Params.get('global', 'trigger_script')
        self.rundown_mode = Params.get('global', 'rundown_mode')
        self.poll_rate = "360" # 6 minutes, gives us battery life hours in 0.1 increments.

    def _record_phase_time(self, phase_name, start_time, duration):
        if Params.get('global', 'phase_reporting') == "1":
            file_path = self.result_dir + os.sep + 'phase_time.csv'
            start_time = start_time - self.daq_start_time
            if not os.path.exists(file_path):
                with open(file_path, 'a', newline='') as f:
                    csv_writter = csv.writer(f)

                    title = ['phase', 'time', 'duration']
                    csv_writter.writerow(title)

                    phase_time = [phase_name, "{:.1f}".format(
                        start_time), "{:.1f}".format(duration)]
                    csv_writter.writerow(phase_time)
            else:
                with open(file_path, 'a', newline='') as f:
                    csv_writter = csv.writer(f)
                    phase_time = [phase_name, "{:.1f}".format(
                        start_time), "{:.1f}".format(duration)]
                    csv_writter.writerow(phase_time)

            if phase_name == "DAQ: DAQStopTime":
                with open(file_path) as f:
                    row_count = sum(1 for row in f)

                if row_count == 3:
                    os.remove(file_path)

    def get_toolCallBacks_result(self):
        return self.toolCallBacks_failed

    @classmethod
    def reset_toolCallBacks_result(cls):
        cls.toolCallBacks_failed = False
        cls.toolCallBacks_backtrace = []
        cls.tool_failure_reason = None

    @classmethod
    def set_toolCallBacks_result(cls, new_val, backtrace):
        traceback_str = ''.join(traceback.format_tb(backtrace.__traceback__))

        cls.toolCallBacks_failed = new_val
        cls.toolCallBacks_backtrace.append(traceback_str)

    def setUp(self, callback_test_begin=None):
        if self.tool_failure_reason is not None:
            self.fail(self.tool_failure_reason)

        logging.debug("ORDER app_scenario setUp: " + self._module)
        Params.dumpResolved()

        # Make sure ffmpeg left over from a previous scenario isn't still running on the DUT
        logging.debug("Stopping ffmpeg: launched = " +
                      str(self.ffmpeg_launched))
        if self.platform.lower() == "windows" and not self.ffmpeg_launched:
            self._call(
                ["cmd.exe", '/c taskkill /IM ffmpeg.exe /T /F > null 2>&1'], expected_exit_code="")

        # Initialize tools
        self.toolCallBacks("initCallback")
        # if self.is_tool == False:
        #     for tool_instance in self.tool_instances:
        #         tool_instance.initCallback(self)

        # Gather run info
        module = self._module
        test_name = module
        if (Params.get('global', 'module_name') != ""):
            test_name = Params.get('global', 'module_name')

        
        url = ""
        if self.dashboard_url != '':
            url = urlunparse(
                urlparse(self.dashboard_url)._replace(
                    path="/result/Results",
                    query="path=" + self.result_dir
                )
            )

        # Write run info
        runInfoFilePath = self.result_dir + os.sep + 'run_info.csv'
        with open (runInfoFilePath,'w', newline='') as runInfoFile:
            csv_writter = csv.writer(runInfoFile)
            csv_writter.writerow(['Run Path', self.result_dir])
            csv_writter.writerow(['Run URL', url])
            csv_writter.writerow(['Run Type', Params.get('global', 'run_type', log = False)])
            try:
                run_number = int(self.result_dir[-3:])
            except:
                run_number = "0"
            csv_writter.writerow(['Run Number', str(run_number)])
            csv_writter.writerow(['Test Name', test_name])
            csv_writter.writerow(['Scenario', module])

        # Start config info, including SoC
        if Params.get('global', 'config_check') != '0' and self.training_mode != '1' and self.collection_enabled != '0' and self.is_prep == False:
            logging.info("Running pre-config_check.")

            # Write hobl version
            hobl_ver = "Unknown"
            try:
                with open("hobl_version.txt", "r") as fo:
                    hobl_ver = fo.readline(50).strip()
            except Exception as e:
                logging.warning(f"Failed to read hobl_version.txt: {e}")

            override_dict = {}
            override_dict["Hardware Version"] = Params.get('global', 'hardware_version', log = False)
            # override_dict["Accessories"] = Params.get('global', 'accessories', log = False)
            override_dict['HOBL Version'] = hobl_ver.strip()
            override_dict['Study Type'] = Params.get('global', 'study_type', log = False)
            override_dict['Product'] = Params.get('global', 'product', log = False)
            override_str = json.dumps(override_dict)
            override_str = override_str.replace('"', "'")
            # override_str = override_str.replace(' ', "")

            if self.platform.lower() == "windows":
                self._upload("utilities\\open_source\\config_check.ps1", self.dut_exec_path, check_modified=True)
                cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1 -LogFile " + self.dut_data_path, "Config") + " -OverrideString " + '\\\"' + override_str + '\\\""'
                self._call(["powershell.exe", cmd])
            elif self.platform.lower() == "macos":
                source = os.path.join("utilities", "open_source", "config_check.sh")
                dest = self.dut_exec_path + "/config_check.sh"
                self._upload(source, self.dut_exec_path, check_modified=True)
                cmd = f'-c "{dest} --logfile={self.dut_data_path}/Config --override-string=\\\"{override_str}\\\""'
                # cmd = f'-c "{dest} --logfile=/Users/powertest/Config"'
                self._call(["zsh", cmd])




            override_str = f"{{'Scenario':'{module}','Test Name':'{test_name}'}}"
            # override_str = f"{{'Test Name':'{test_name}'}}"
            # override_str = f"{{'Scenario':'{module}'}}"
            # print('override string used for traige the configcheck scenario issue:   ' + override_str)
            cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1") + " -Prerun -LogFile " + '\\\"' + os.path.join(
                self.dut_data_path, self.testname + "_ConfigPre") + '\\\"' + "-OverrideString " + '\\\"' + override_str + '\\\""'
            if self.platform.lower() == "android":
                # result = self._host_call('python .\\utilities\\Android\\config_check_android.py --PreRun --OverrideString \'"' + override_str.replace("'", '"""') + '"\' --LogFile ' + self.result_dir + '\\' + self.testname + '_ConfigPre' + " -i " + str(self.dut_ip) + ":5555", expected_exit_code="")
                result = self._host_call('python .\\utilities\\Android\\config_check_android.py --PreRun --OverrideString "' + '\\\"' + override_str +
                                         '\\\"" --LogFile ' + self.result_dir + '\\' + self.testname + '_ConfigPre' + " -i " + str(self.dut_ip) + ":5555", expected_exit_code="")
            elif self.platform.lower() == "wcos":
                result = self._call(["pwsh.exe", cmd])
                if "config_check.ps1' is not recognized" in result:
                    logging.error(
                        "Please run config_check_prep scenario to put the config_check script on the DUT.")
            elif self.platform.lower() == "windows":
                result = self._call(["powershell.exe", cmd])
                if "config_check.ps1' is not recognized" in result:
                    logging.error(
                        "Please run config_check_prep scenario to put the config_check script on the DUT.")
            elif self.platform.lower() == "macos":
                dest = self.dut_exec_path + "/config_check.sh"
                cmd = f'-c "{dest} --prerun --logfile={self.dut_data_path}/{self.testname}_ConfigPre --override-string=\\\"{override_str}\\\""'
                # cmd = f'-c "{dest} --prerun --logfile={self.dut_data_path}/{self.testname}_ConfigPre"'
                result = self._call(["zsh", cmd])
            # Copy back results - Commenting out for now because trying to copy back while screen_recording causes tar failure on SimpleRemote, and I don't see the need for it anyway.
            # logging.debug("Copying data from DUT in setUp.")
            # self._copy_data_from_remote(self.result_dir)

            # Idea is to prevent wasting time with execution when USB devices are accidentally attached, but 2 problems:
            #   1. Sometimes we need to test with devices attached, and the prompt prevents automated excecution.
            #   2. Doesn't work with remote execution.  Looking for the file in the result dir should work with both remote and local execution.
            # with open(PreRunFile) as json_data:
            #     d = json.load(json_data)
            #     if d["Foreign Device Found"] == "1":
            #         MessageToDisplay = '"Foreign Device Detected. Press OK to Continue.  Press CANCEL to Exit."'
            #         self._host_call('c:\\hobl\\utilities\\MsgPrompt.exe -MSG ' + MessageToDisplay  + ' -t 90')

        # Trigger test begin callbacks for tools:
        self.toolCallBacks("testBeginCallback")

        # logging.debug("self.trace=" + str(self.trace))
        # logging.debug("self.training_mode=" + str(self.training_mode))
        # logging.debug("self.collection_enabled=" + str(self.collection_enabled))
        
        # Get trace providers before checking if we need to start an etl trace
        self.trace_providers = Params.getCalculated("trace_providers")

        if self.trace_providers != '' and self.training_mode != '1' and self.collection_enabled != '0':
            logging.debug("self._module = " + str(self._module))

            # Cancel any existing traces first.
            self._call(
                ["cmd.exe", "/c wpr.exe -cancel > null 2>&1"], expected_exit_code="")
            
            # Getting built in providers to support that as well when calling for etl providers
            output = self._call(["cmd.exe", "/c wpr.exe -profiles"], expected_exit_code="")
            lines = output.strip().split('\n')
            built_in_profiles = [line.split()[0].lower() for line in lines[2:] if line.strip()]
            

            provider_list = self.trace_providers.split()
            provider_list = list(set(provider_list)) #remove any duplicate wprp files
            wpr_command = ""

            for profile in provider_list:
                try:
                    # Checking if provider provided was a built in one. 
                    if profile.lower() in built_in_profiles:
                        logging.debug("Profile " + profile + " is a built in profile, no need to upload.")
                        wpr_command = wpr_command + " -start " + profile
                        continue

                    logging.debug("Attempting to move " + profile)
                    self._upload(self.resolve("providers\\" + profile), self.dut_exec_path)

                    wpr_command = wpr_command + " -start " + self.dut_exec_path + "\\" + profile
                except:
                    raise Exception("Couldn't find provider " + profile)
                    

            # Start ETL trace. In filemode use an instance name so we can avoid collisions with existing tracing sessions.
            try:
                if Params.get('global', 'trace_filemode') == '1':
                    self._call(["cmd.exe", "/c wpr.exe" + wpr_command + " -filemode -instancename perfTrace"])
                else:
                    self._call(["cmd.exe", "/c wpr.exe" + wpr_command])
            except Exception as e:
                err_msg = str(e)
                if "-984076287" in err_msg or "0xc5583001" in err_msg.lower():
                    logging.warning("WPR reported profiles already running. Retrying trace start after cancel.")
                    self._call(["cmd.exe", "/c wpr.exe -cancel -instancename perfTrace > null 2>&1"], expected_exit_code="")
                    self._call(["cmd.exe", "/c wpr.exe -cancel > null 2>&1"], expected_exit_code="")
                    if Params.get('global', 'trace_filemode') == '1':
                        self._call(["cmd.exe", "/c wpr.exe" + wpr_command + " -filemode -instancename perfTrace"])
                    else:
                        self._call(["cmd.exe", "/c wpr.exe" + wpr_command])
                else:
                    raise

            # Mark beginning of test
            if Params.get('global', 'trace_filemode') == '1':
                self._call(["cmd.exe", '/c wpr.exe -marker "test_begin" -instancename perfTrace'])
            else:
                self._call(["cmd.exe", '/c wpr.exe -marker "test_begin"'])
            self.trace_started = True

        # Trigger global test begin callback
        if callback_test_begin == None:
            self._callback(Params.get('global', 'callback_test_begin'))
        else:
            self._callback(callback_test_begin)

    def runScenario(self):
        self.scenario_start_time = time.time()
        self.scenario_prev_time = self.scenario_start_time
        self.scenario_accumulated_time = 0
        self.log_scenario_events = True
        if self.is_prep == False:
            logging.info("Record phase time: Measurement start")
            self.daq_accumulated_time = 0
            self.daq_start_time = time.time()
            self.daq_prev_time = self.daq_start_time
            self._record_phase_time('DAQ: DAQStartTime', self.daq_start_time, 0)
        self.runWithThreads()

    def runTestWrapper(self):
        # logging.debug("Wrapping runTest method to take a screenshot upon exception.")
        try:
            prep = getattr(self, "prep", None)
            if callable(prep) and self.prep_run_only:
                self.prep()
            else:
                self.runTest()
        except Exception as exp:
            if self.rundown_mode == "0":
                self.logErrorMessages(exp, path=self.__module__.split(".")[-2])
            if self._module != "comm_check":
                try:
                    if self.stop_soc == "0":
                        time.sleep(60)
                    if self.platform.lower() != 'android':
                        rpc.call_rpc(self.dut_ip, self.rpc_port,
                                     "GetVersion", [])

                    self._screenshot(name="failedscreen.png")
                    logging.debug(
                        "Copying data from DUT due to test exception.")
                    self._copy_data_from_remote(self.result_dir)

                    if self.platform.lower() != 'android':
                        rpc.call_rpc(self.dut_ip, self.rpc_port, "GetVersion", [])
                    
                    if isinstance(exp, NoSuchElementException) or isinstance(exp, TimeoutException):
                        logging.info("Launching Driver to Capture XML Dump.")
                        try:
                            if self.platform.lower() == 'android':
                                # Create a temporary driver
                                desired_caps = {}
                                desired_caps["udid"] = self.dut_ip + ":5555"
                                desired_caps["automationName"] = "UIAutomator2"
                                desired_caps["platformVersion"] = self.platformVersion
                                desired_caps["platformName"] = 'Android'
                                desired_caps["deviceName"] = '235a269a'
                                desired_caps["noReset"] = True
                                desired_caps["newCommandTimeout"] = 10000
                                desired_caps["systemPort"] = self.systemPort
                                temp_driver = self._launchApp(desired_caps)

                                # Dump the page source
                                self._page_source(temp_driver)
                                temp_driver.close()

                            else:
                                # Start WinAppDriver
                                self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"),
                                           (self.dut_resolved_ip + " " + self.app_port)], blocking=False)
                                time.sleep(1)

                                # Create a temporary driver
                                desired_caps = {}
                                desired_caps["app"] = "Root"
                                temp_driver = self._launchApp(
                                    desired_caps, track_driver=False)

                                # Dump the page source
                                self._page_source(temp_driver)
                                temp_driver.close()

                        except Exception as e:
                            logging.error(
                                "Unable to find element! Unable to dump page source! " + e)
                            # pass
                except:
                    self.toolCallBacks("testTimeoutCallback")
                    if self.platform.lower() != 'android':
                        self.dut_conn_timeout = True
                        self._wait_for_dut_comm()
            self.toolCallBacks("testScenarioFailed")
            logging.debug("Copying data from DUT due to test exception again.")
            self._copy_data_from_remote(self.result_dir)
            raise exp

    # implement in derived scenario
    # def runTest(self):
    #     logging.error("runTest method not defined in Scenario!")
    #     raise Exception("runTest method not defined!")

    def toolCallBacks(self, method_name, fail_pass=False, log=True):
        if self.is_tool:
            return
        for tool_instance in self.tool_instances:
            if method_name not in dir(tool_instance):
                continue
            tool_module = type(tool_instance).__module__.split('.')[-1]
            if log:
                logging.debug("ORDER app_scenario calling tool " + str(method_name) + " for: " + tool_module)
            if (method_name == "initCallback" or method_name == "testBeginEarlyCallback"):
                getattr(tool_instance, method_name)(self)
            elif (method_name == "toolStatusCallback"):
                statusCode, error_msg = getattr(tool_instance, method_name)()
                if statusCode == -1 or statusCode == 1:
                    return statusCode, error_msg
            else:
                try:
                    getattr(tool_instance, method_name)()
                except Exception as e:
                    self.logErrorMessages(e)
                    if fail_pass == True:
                        self.set_toolCallBacks_result(True, e)
                        pass
                    else:
                        raise e
        # if method was toolStatusCallback and we reach the end then we want to return 0 signinaling nothing wrong.
        if method_name == "toolStatusCallback":
            return 0, "continue test"

    def logErrorMessages(self, exp, path="hobl\\tools", trace=None):
        if trace:
            trc = trace
        else:
            trc = traceback.format_tb(exp.__traceback__)
        exit_app = False
        for ind, val in enumerate(trc):
            if (exit_app and "hobl\\scenarios\\app_scenario" in val) or (exit_app and path not in val):
                x = trc[ind-1].split("File ")[1].split(",")
                logging.error('{0}: {1}, {2}'.format(
                    type(exp).__name__, x[0], x[1]))
                return
            if "hobl\\scenarios\\app_scenario" not in val:
                exit_app = True
        if exit_app and path in trc[-1]:
            x = trc[-1].split("File ")[1].split(",")
            logging.error('{0}: {1}, {2}'.format(
                type(exp).__name__, x[0], x[1]))

    def monitorLife(self):
        logging.info("Life monitoring thread started")
        # Poll DUT to see if it's still responsive, if not, raise timeout exception
        file_path = self.result_dir + os.sep + 'battery_level.txt'
        while(True):
            try:
                if self.platform.lower() == 'windows':
                    if int(self.stop_soc) <= 0:
                        batt_level = self._call(["powershell.exe", "Add-Type -Assembly System.Windows.Forms; [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)"], timeout=30)
                        logging.info(f"Battery level: {batt_level}")
                        # rpc.call_rpc(self.dut_ip, self.rpc_port, "GetVersion", [])
                        # logging.info("DUT is alive")
                        # Use RTC timer
                        self._kill("RTCWakeCore.exe")
                        self._call([os.path.join(self.dut_exec_path, "RTCWakeCore", "RTCWakeCore.exe"), '-duration 1800'], blocking=False, timeout=30)
                        # logging.info("RTC Wake timer reset")
                    time.sleep(900)
                elif self.platform.lower() == 'macos':
                    result = self._call(["pmset", "-g batt"], blocking=True)
                    level = result.split("\n")[1].split("\t")[1].split("%")[0]
                    current_time = datetime.now()
                    time_s = current_time.strftime("%m/%d/%Y %I:%M:%S %p")
                    logging.info(f"Battery level: {level}")
                    with open(file_path, 'a', newline='') as f:
                        f.write(f"{time_s}: total battery: {level}\n")
                    if int(level) <= int(self.stop_soc):
                        break
                    time.sleep(int(self.poll_rate))
                else:
                    time.sleep(900)
            except Exception:
                self.toolCallBacks("testTimeoutCallback")
                if self.platform.lower() != 'android':
                    self.dut_conn_timeout = True
                    self._wait_for_dut_comm()
                self.toolCallBacks("testScenarioFailed")
                logging.debug("Copying data from DUT due to test exception again.")
                self._copy_data_from_remote(self.result_dir)
                raise Exception("Device monitor timeout")

    def monitorBattery(self):
        logging.info("Monitoring battery rundown to: " + str(self.stop_soc))
        if self.platform.lower() == "android":
            while int(self.getAndroidBatt(self.dut_ip)) > int(self.stop_soc):
                time.sleep(int(self.poll_rate))
        elif self.platform.lower() == "macos":
            # file_path = self.result_dir + os.sep + 'battery_level.txt'
            # while(True):
            #     result = self._call(["pmset", "-g batt"], blocking=True)
            #     level = result.split("\n")[1].split("\t")[1].split("%")[0]
            #     current_time = datetime.now()
            #     time_s = current_time.strftime("%m/%d/%Y %I:%M:%S %p")
            #     logging.info(f"Battery level: {level}")
            #     with open(file_path, 'a', newline='') as f:
            #         f.write(f"{time_s}: total battery: {level}\n")
            #     if int(level) <= int(self.stop_soc):
            #         break
            #     time.sleep(int(self.poll_rate))
            time.sleep(172800)  # 48 hours, just to keep the thread alive, we will stop it when the scenario ends.
        elif int(self.stop_soc) <= 0:
            self._kill("MonitorPowerEvents.exe")
            logging.info("we are entering stop_soc set to 1")
            self._call([os.path.join(self.dut_exec_path, "MonitorPowerEvents.exe"),
                       "/stopsoc=1" + " /execpath=" + str(self.dut_exec_path) + "\\RTCWakeCore" + " /datapath=" + str(self.dut_data_path) + " /testname=" + str(self.testname) + " /triggerpercent=" + str(self.trigger_soc) + " /triggerscript=" + str(self.trigger_script)],
                        blocking=True, timeout=172800, expected_exit_code="")
        else:
            self._kill("MonitorPowerEvents.exe")
            self._call([os.path.join(self.dut_exec_path, "MonitorPowerEvents.exe"), "/stopsoc=" +
                       str(self.stop_soc)], blocking=True, timeout=172800, expected_exit_code="")
        logging.info("Battery monitor End")

    def checkToolStatus(self, statusCode):
        # statusCode = 0 # -1 = tool is initiating failure and stopping test, 0 = nothing wrong let scenario continue, 1 = tool has initiated a pass and stopping test. 
        while(statusCode == 0):
            time.sleep(10)
            statusCode, error_msg = self.toolCallBacks("toolStatusCallback", log=False)
        if statusCode == -1:
            raise Exception("Tool has initiated a failure. Stopping test. Error msg: " + error_msg)

    def runWithRundown(self):
        logging.debug("Creating Run with Rundown Thread")

        # Replace Sleeps with Event Waits
        sleepEvent = threading.Event()
        time.oldsleep = time.sleep
        time.sleep = sleepEvent.wait

        # Thread End Event
        endThreadEvent = threading.Event()

        # Create the exception Event to track thrown exceptions
        scenarioExceptionEvent = threading.Event()
        monitorExceptionEvent = threading.Event()
        lifeExceptionEvent = threading.Event()

        # define the threads
        monitorThread = thread_with_exception(
            "MonitorThread", self.monitorBattery, monitorExceptionEvent, endThreadEvent)
        lifeThread = thread_with_exception(
            "LifeThread", self.monitorLife, lifeExceptionEvent, endThreadEvent)
        scenarioThread = thread_with_exception(
            "ScenarioThread", self.runTestWrapper, scenarioExceptionEvent, endThreadEvent)
        

        # Setting threads as daemons
        monitorThread.setDaemon(True)
        lifeThread.setDaemon(True)
        scenarioThread.setDaemon(True)

        # Start the threads

        try:
            logging.info("Starting Monitor Thread")
            monitorThread.start()
            logging.info("Starting Life Thread")
            lifeThread.start()
            logging.info("Starting Scenario Thread")
            scenarioThread.start()

            # Wait for a thread to end
            logging.info("waiting for threads to end")
            endThreadEvent.wait()

            # Check if the scenario finished before the Monitor Thread
            if (int(self.stop_soc) > 0):
                if monitorThread.is_alive():
                    raise Exception("Scenario Ended Before Monitor Thread")
                else:
                    logging.info("Monitor Thread Ended")
            time.sleep(5)

        finally:
            # End the threads
            monitorThread.raise_exception()
            lifeThread.raise_exception()
            scenarioThread.raise_exception()

            print("Kill Threads")
            for activeThread in self.activeHostCalls:
                activeThread.raise_exception()

            # Trigger the Sleep event
            sleepEvent.set()

            # Revert the time.sleep override
            time.sleep = time.oldsleep

            # Check if Exception occured in other thread (setting event means no exception was raised)
            if (int(self.stop_soc) > 0):
                if (monitorExceptionEvent.is_set() or scenarioExceptionEvent.is_set()):
                    if scenarioExceptionEvent.is_set():
                        exceptionThread = "Scenario Thread"
                    elif monitorExceptionEvent.is_set():
                        exceptionThread = "Monitor Thread"
                    else:
                        exceptionThread = "Batter Life Thread"
                    raise Exception("Exception raised in " +
                                    exceptionThread + ", see logs for details")

            # Do post rundown Stuff
            # Teardown and Kill already run just from default behavior (SetUp->runTest->TearDown->Kill)

    def runWithThreads(self):
        logging.debug("Creating Run with Thread")
        # initiating statusCode which is used for toolStatusThread
        statusCode = 0 

        # Replace Sleeps with Event Waits
        sleepEvent = threading.Event()
        time.oldsleep = time.sleep
        time.sleep = sleepEvent.wait

        # Thread End Event
        endThreadEvent = threading.Event()

        # Create the exception Event to track thrown exceptions
        scenarioExceptionEvent = threading.Event()

        # if tools with threads are enabled then create the exception event for tools
        if self.enable_tool_threading:
            toolsExceptionEvent = threading.Event()

        # Create monitor and life threads if rundown mode is enabled
        if self.rundown_mode == "1":
            monitorExceptionEvent = threading.Event()
            lifeExceptionEvent = threading.Event()

        # define the threads
        if self.rundown_mode == "1":
            monitorThread = thread_with_exception(
                "MonitorThread", self.monitorBattery, monitorExceptionEvent, endThreadEvent)
            lifeThread = thread_with_exception(
                "LifeThread", self.monitorLife, lifeExceptionEvent, endThreadEvent)
        scenarioThread = thread_with_exception(
            "ScenarioThread", self.runTestWrapper, scenarioExceptionEvent, endThreadEvent, rundown = self.rundown_mode)
        if self.enable_tool_threading:
            toolStatusThread = thread_with_exception(
                "ToolStatusThread", self.checkToolStatus, toolsExceptionEvent, endThreadEvent, args=[statusCode])
        

        # Setting threads as daemons
        if self.rundown_mode == "1":
            monitorThread.setDaemon(True)
            lifeThread.setDaemon(True)
        if self.enable_tool_threading:
            toolStatusThread.setDaemon(True)
        scenarioThread.setDaemon(True)


        # Start the threads
        try:
            if self.rundown_mode == "1":
                logging.debug("Starting Monitor Thread")
                monitorThread.start()
                logging.debug("Starting Life Thread")
                lifeThread.start()
            if self.enable_tool_threading:
                logging.debug("Starting Tool Status Thread")
                toolStatusThread.start()
            logging.debug("Starting Scenario Thread")
            scenarioThread.start()

            # Wait for a thread to end
            logging.debug("waiting for threads to end")
            endThreadEvent.wait()

            # Check if the scenario finished before the Monitor Thread if rundown mode
            if self.rundown_mode == "1":
                if (int(self.stop_soc) > 0):
                    if monitorThread.is_alive():
                        raise Exception("Scenario Ended Before Monitor Thread")
                    else:
                        logging.debug("Monitor Thread Ended")
                time.sleep(5)

        finally:
            # End the threads
            if self.rundown_mode == "1":
                monitorThread.raise_exception()
                lifeThread.raise_exception()
            scenarioThread.raise_exception()
            if self.enable_tool_threading:
                toolStatusThread.raise_exception()

            print("Kill Threads")
            for activeThread in self.activeHostCalls:
                activeThread.raise_exception()

            # Trigger the Sleep event
            sleepEvent.set()

            # Revert the time.sleep override
            time.sleep = time.oldsleep

            # Check if Exception occured in other thread (setting event means no exception was raised)
            if self.rundown_mode == "1":
                if (int(self.stop_soc) > 0):
                    if (monitorExceptionEvent.is_set() or scenarioExceptionEvent.is_set()):
                        if scenarioExceptionEvent.is_set():
                            exceptionThread = "Scenario Thread"
                        elif monitorExceptionEvent.is_set():
                            exceptionThread = "Monitor Thread"
                        else:
                            exceptionThread = "Battery Life Thread"
                        raise Exception("Exception raised in " +
                                        exceptionThread + ", see logs for details")
                    
            elif scenarioExceptionEvent.is_set():
                raise Exception(scenarioThread.errormsg)
            
            if self.enable_tool_threading:
                if toolsExceptionEvent.is_set():
                        raise Exception(toolStatusThread.errormsg)
                # if (scenarioExceptionEvent.is_set() or toolsExceptionEvent.is_set()):
                #     if scenarioExceptionEvent.is_set():
                #         exceptionThread = "Scenario Thread"
                #         raise Exception(scenarioThread.errormsg)
                #     elif toolsExceptionEvent.is_set():
                #         exceptionThread = "Tool Status Thread"
                #         raise Exception(toolStatusThread.errormsg)
                    # raise Exception("Exception raised in " +
                    #                 exceptionThread + ", see logs for details")




            # Do post rundown Stuff
            # Teardown and Kill already run just from default behavior (SetUp->runTest->TearDown->Kill)

    def getAndroidBatt(self, device_ip=None):
        disconnect = False
        batt_attempt = 0

        # Build the command first
        command = "adb "
        if device_ip is not None:
            command = command + "-s " + str(device_ip) + ":5555 "
        command = command + "shell \"dumpsys battery | grep 'level'|cut -f2 -d ':'\""

        # NOTE: Try to keep this block short
        with self.adbLock:
            # connect if disconnected
            while (not (self.dut_ip in self._host_call("adb devices", expected_exit_code=""))) and batt_attempt < 3:
                disconnect = True
                batt_attempt += 1

                logging.info("Not Connected to device, connecting to " +
                             str(self.dut_ip) + " Attempt: " + str(batt_attempt))
                logging.info(self._host_call(
                    "adb connect " + str(self.dut_ip) + ":5555", expected_exit_code="", timeout=60))

            # Check battery level with built command
            adb_attempt = 0
            while adb_attempt <= 3:
                try:
                    out = self._host_call(
                        command, expected_exit_code="", timeout=10)
                    break
                except:
                    adb_attempt += 1
                    logging.error(
                        "Unable to get battery level, Attempt: ", adb_attempt)
                    pass

            if adb_attempt >= 3:
                raise Exception("Unable to read Battery Level!")

            # disconnect if needed
            if disconnect:
                logging.info("Disconnecting from " + str(self.dut_ip))
                logging.info(self._host_call(
                    "adb disconnect " + str(self.dut_ip) + ":5555", expected_exit_code="", timeout=60))

        # exit_code = p.returncode
        logging.info("Battery level: " + str(int(out)))
        return (int(out))

    def tearDown(self, callback_test_end=None, callback_data_ready=None):
        logging.info("Entered teardown")
        try:
            # Quit driver(s)
            for driver in self.drivers:
                driver.quit()
        except:
            logging.debug("Connection timeout during driver quit")
            pass

        logging.info("triggering endtest callback")
        # Trigger endTest callback
        if callback_test_end == None:
            self._callback(Params.get('global', 'callback_test_end'))
        else:
            self._callback(callback_test_end)

        # if self.training_mode != '1' and (self.testname[:-4] == "abl" or self.testname[:-4] == "abl_active"):
        # if self.is_prep == False and callback_test_end != "" and self.training_mode != '1' and self.collection_enabled != '0':
        if self.is_prep == False:
            logging.info("Record phase time: Measurement stop")
            self._record_phase_time('DAQ: DAQStopTime', time.time(), 0)

        try:
            self.toolCallBacks("testEndCallback", fail_pass=True)
        except Exception as e:
            self.set_toolCallBacks_result(True, e)
            pass

        if self.trace_providers != "" and self.training_mode != '1' and self.collection_enabled != '0':
            if self.trace_started:
                if self.dut_conn_timeout:
                    #logging.info("Ending trace and cancelling etl tracing")
                    self._call(
                        ["cmd.exe", "/c wpr.exe -cancel > null 2>&1"], expected_exit_code="")
                else:
                    # Mark end of test
                    if Params.get('global', 'trace_filemode') == '1':
                        self._call(["cmd.exe", '/c wpr.exe -marker "test_end" -instancename perfTrace'])
                    else:
                        self._call(["cmd.exe", '/c wpr.exe -marker "test_end"'])
                    # Stop ETL trace
                    outfile = os.path.join(
                        self.dut_data_path, self.testname + ".etl")

                    logging.info("Ending trace and saving at: " + outfile)
                    if Params.get('global', 'trace_filemode') == '1':
                        self._call(["cmd.exe", f"/c wpr.exe -stop {outfile} -compress -instancename perfTrace"])
                    else:
                        self._call(["cmd.exe", f"/c wpr.exe -stop {outfile} -compress"])
                self.trace_started = False

        # Stop config info
        if Params.get('global', 'config_check') != '0' and self.training_mode != '1' and self.collection_enabled != '0' and self.is_prep == False and int(self.stop_soc) > 0:
            logging.info("Running post-config_check.")
            cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1") + " -PostRun -LogFile " + '\\\"' + os.path.join(
                self.dut_data_path, self.testname + "_ConfigPost") + '\\\"' + " -PreRunFile " + '\\\"' + os.path.join(self.dut_data_path, self.testname + "_ConfigPre.csv") + '\\\"'
            # cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1 -PostRun -LogFile " + self.dut_data_path, self.testname + "_ConfigPost -PreRunFile " + self.dut_data_path, self.testname + "_ConfigPre.json") + '"'
            if self.platform.lower() == "android":
                try:
                    self._host_call('python .\\utilities\\Android\\config_check_android.py --PostRun --LogFile ' + self.result_dir + '\\' + self.testname + "_ConfigPost" +
                                    " --PreRunFile " + self.result_dir + "\\" + self.testname + "_ConfigPre.csv" + " -i " + str(self.dut_ip) + ":5555", expected_exit_code="", timeout=90)
                except:
                    logging.error("Post Config exception!: " +
                                  traceback.format_exc())
            elif self.platform.lower() == "wcos":
                result = self._call(["pwsh.exe", cmd])
            elif self.platform.lower() == "windows":
                # self._call(["powershell.exe", "-ExecutionPolicy Unrestricted " + os.path.join(self.dut_exec_path, "config_check.ps1 -PostRun -LogFile " + self.dut_data_path + "\\" + self.testname + "_ConfigPost" + " -PreRunFile " + self.dut_data_path + "\\" + self.testname + "_ConfigPre.json")], system = True)
                result = self._call(["powershell.exe", cmd])
            elif self.platform.lower() == "macos":
                dest = self.dut_exec_path + "/config_check.sh"
                cmd = f'-c "{dest} --postrun --logfile={self.dut_data_path}/{self.testname}_ConfigPost --prerunfile={self.dut_data_path}/{self.testname}_ConfigPre.csv"'
                result = self._call(["zsh", cmd])

        # Copy back results
        if self.collection_enabled != '0':
            logging.debug("Copying data from DUT in tearDown.")
            self._copy_data_from_remote(self.result_dir)

        # TODO: Calculate power drain, other stats, write results.

        # TODO: Check against expectations?

        # Tool Data Ready Callback
        self.toolCallBacks("dataReadyCallback", fail_pass=True)

        # Framework Data Ready Callback
        self._callback(Params.get('global', 'callback_data_ready'))

        if(self.rundown_mode == "1" and int(self.stop_soc) == 0):
            self.check_battery_level()
            self.config_full_dur()

        # Tool Report Callback
        self.toolCallBacks("reportCallback", fail_pass=True)

        # Reset time tracking after potentially long delays in callbacks.
        self.scenario_start_time = self.scenario_prev_time = time.time()
        self.daq_accumulated_time = self.scenario_accumulated_time = 0
        self.daq_start_time = time.time()
        self.daq_prev_time = self.daq_start_time
        self.log_scenario_events = False


    @classmethod
    def tearDownClass(cls):
        if cls.toolCallBacks_failed == True:
            counter = 1
            traceback_msg = ''
            for x in cls.toolCallBacks_backtrace:
                traceback_msg += '\nBacktrace {0} : \n '.format(counter)
                traceback_msg += ''.join(y for y in cls.toolCallBacks_backtrace)
                counter += 1
            cls.fail(cls, msg=traceback_msg)
            pass

    def _callback(self, cb):
        if self.is_prep == False and cb != "" and self.training_mode != '1' and self.collection_enabled != '0':
            output = self._host_call(cb + " " + os.path.abspath(self.result_dir))
            if "CALLBACK_TIMEOUT" in output:
                logging.error("CALLBACK_TIMEOUT for " + cb)
                fail_callback = Params.get("global", "callback_test_fail")
                if fail_callback != "":
                    output2 = self._host_call(fail_callback + " " + os.path.abspath(self.result_dir))
                self.fail()           

    # Start Win App Driver on the DUT
    def _startWinAppDriver(self, winAppDriverPath=None):
        if winAppDriverPath is None:
            winAppDriverPath = self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"
        self._call([winAppDriverPath, self.dut_resolved_ip + " " + self.app_port + " /forcequit"], blocking=False)
        time.sleep(1)

    # Create a new driver for the DUT
    def _launchApp(self, desired_caps, track_driver = True):
        # If desired_caps is a string, convert it to a dictionary with desired_caps["app"] = desired_caps
        if type(desired_caps) is not dict:
            _desired_caps = {}
            _desired_caps["app"] = desired_caps
            desired_caps = _desired_caps
        
        if self.platform.lower() == 'android':
            dut_url = "http://127.0.0.1:" + self.app_port #+ "/wd/hub" # removed this part for appium 2.0
            # Remove port forwarding on android dut
            self._host_call("adb -s " + self.dut_ip + ":5555 forward --remove tcp:" + str(Params.get('global', 'systemPort')), expected_exit_code="")
        else:
            dut_url = "http://" + self.dut_resolved_ip + ":" + self.app_port
            desired_caps["ms:experimental-webdriver"] = True
        RemoteConnection.set_timeout(None)
        driver = webdriver.Remote(command_executor = dut_url, desired_capabilities = desired_caps)
        # driver = selenium_wd.Remote(command_executor = RemoteConnection(dut_url, resolve_ip=False), desired_capabilities = desired_caps)
        # driver = webdriver.Remote(command_executor = RemoteConnection(dut_url, resolve_ip=False), desired_capabilities = desired_caps)
        if track_driver == True:
            self.drivers.append(driver)
        return driver

    def _launchDesktop(self, track_driver = True):
        return self._launchApp("Root", track_driver)

    def _launchWeb(self, desired_caps):
        app_port = Params.get('global', 'web_port')
        dut_url = "http://" + self.dut_ip + ":" + app_port
        driver = webdriver.Remote(
            command_executor = dut_url,
            desired_capabilities = desired_caps)
        self.drivers.append(driver)
        return driver

    def _getDriverFromWinName(self, top_driver, win_name):
        driver = self.getDriverFromWin(WebDriverWait(top_driver, 20).until(EC.presence_of_element_located((By.NAME, win_name))))
        return driver


    def getWindowHandle(self, win):
        win_handle1 = win.get_attribute("NativeWindowHandle")
        win_handle2 = int(win_handle1)
        win_handle3 = format(win_handle2, 'x') # convert to hex string
        return win_handle3


    def getDriverFromWin(self, win):
        win_handle = self.getWindowHandle(win)

        # Launch new session attached to the window
        desired_caps = {}
        desired_caps["appTopLevelWindow"] = win_handle
        driver = self._launchApp(desired_caps, track_driver = False)
        time.sleep(2)  
        driver.switch_to_window(win_handle)
        # driver.maximize_window()
        return driver


    '''
    expected_exit_code == equals to "" , do not check exit_code
    if not and it is not equal to expected_exit_code, then it fails
    '''
    def _call(self, command, system=True, blocking=True, callback=False, port="", expected_exit_code="0", fail_on_exception=True, log_output=True, timeout=1800, target_ip="", priority="Normal"):
        if port == "":
            port = self.rpc_port
        if target_ip == "":
            target_ip = self.dut_ip

        # logging.info("Calling: ", command)
        if False:
            pass
        # if Params.get('global', 'local_execution') == '1':
        #     cmd_str = " ".join(command)
        #     logging.debug("Calling local subprocess: " + str(cmd_str))  
            
        #     return(self._host_call(command=cmd_str, expected_exit_code=expected_exit_code, blocking=blocking))
        else:
            if blocking == True and callback == False and self.async_comm == "1":
                if log_output:
                    logging.debug("Call - blocking with callback.  host_ip = " + self.host_ip)

                # Make socket connection
                range_low = int(Params.get('global', 'port_range_low'))
                range_high = int(Params.get('global', 'port_range_high'))
                skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if range_high == 0:
                    skt.bind((self.host_ip, 0))
                else:
                    count = 0
                    while(True):
                        try:
                            _port = random.randint(range_low, range_high)
                            logging.debug("Trying port " + str(_port))
                            skt.bind((self.host_ip, _port))
                            break
                        except:
                            count += 1
                        if count > 10:
                            logging.error("Can't find free port in specified range.")
                            self.fail("Can't find free port in specified range.")

                skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                callback_port = skt.getsockname()[1]

                result = rpc.call_rpc(target_ip, port, "StartJobWithNotification", command, self.host_ip, callback_port, log=log_output, timeout=timeout, priority=priority)

                output = ""
                try:
                    output = json.loads(result)
                except Exception as e:
                    logging.error("Exception decoding JSON: " + str(e))
                    logging.error("Result: " + str(result))
                    raise Exception('Exception decoding JSON')
                if "result" in output:
                    jobid = output["result"]
                else:
                    if fail_on_exception and "error" in output:
                        error = output["error"]
                        logging.error(error)
                        raise Exception('Call failed. Check error information')
                    else:
                        logging.debug(result)
                    return output

                output = ""
                callback_result = self._wait_for_rpc_callback(jobid = jobid, skt = skt, host = self.host_ip, port = callback_port, log_output=log_output, timeout = timeout, target_ip=target_ip)
                # fail test if call_rpc returns CALLBACK
                if callback_result == "CALLBACK":
                    self.fail(msg = 'call_rpc timeout to SimpleRemote')
                callback_result_json = json.loads(callback_result)
                if "result" in callback_result_json:
                    result = json.loads(callback_result_json["result"])
                    # logging.debug(f"Result: {result}")
                    if "output" in result:
                        output = result["output"].strip("\r\n")
                        if fail_on_exception and "Exception" in output:
                            error_lines = output.split('\n')
                            for error in error_lines:
                                logging.error(error.strip("\r\n"))
                            # if fail_on_exception:
                            raise Exception('Call failed. Check error information')
                            # else:
                            #     logging.error("*** The above errors are not considered fatal.")
                        else:
                            if log_output:
                                logging.debug("Output:\n" + output)
                    if "exitCode" in result:
                        actual_exit_code = str(result["exitCode"])
                        Params.setCalculated('last_call_exit_code', actual_exit_code)
                        # logging.debug(f"Exit code: {actual_exit_code}")
                        if(expected_exit_code !=""):
                            if actual_exit_code != expected_exit_code :
                                raise Exception('The call\'s exit code {0} doesn\'t match with expected exit code {1}'.format(actual_exit_code, expected_exit_code))

                # return callback_result
                return output
            elif blocking == True and callback == False and self.async_comm == "0":
                # logging.info("Calling RPC RunWithResult: " + str(command))
                # print("Call:", command)

                result = rpc.call_rpc(target_ip, port, "RunWithResultAndExitCode", command, log=log_output, timeout=timeout, priority=priority)

                # fail test if call_rpc returns CALLBACK
                if result == "CALLBACK":
                    self.fail(msg = 'call_rpc timeout to SimpleRemote')

                output = json.loads(result)

                if ("result" in output and "Exception" in output["result"]) or "ERROR" in output or "error" in output:
                    if "result" in output:
                        result = output["result"]
                    elif "ERROR" in output:
                        result = output["ERROR"]
                    else:
                        result = output["error"]
                    logging.error("Error:\n" + result)
                    raise Exception('Call failed. Check error information')
                if "result" in output and "Exception" not in output["result"] :
                    result = output["result"][1].strip("\r\n")
                    logging.debug("Result:\n" + result)
                    if(expected_exit_code !=""):
                        actual_exit_code = output["result"][0]
                        Params.setCalculated('last_call_exit_code', actual_exit_code)
                        if actual_exit_code != expected_exit_code :
                            raise Exception('The call\'s exit code {0} doesn\'t match with expected exit code {1}'.format(actual_exit_code, expected_exit_code))
                if "ERROR" not in output and "error" not in output and "result" not in output:
                    logging.debug("Output Information:\n" + output)
                return result
            else:
                # if callback == True:
                #     # To do this properly, need to bind listener befor issuing command
                #     # logging.info("Calling RPC StartJobWithNotification: " + str(command))
                #     result = rpc.call_rpc(target_ip, port, "StartJobWithNotification", command, self.host_ip, self.rpc_callback_port, timeout=timeout)

                #     # fail test if call_rpc returns CALLBACK
                #     if result == "CALLBACK":
                #         self.fail(msg = 'call_rpc timeout to SimpleRemote')

                #     logging.debug(result)
                #     return result                    
                # else:
                
                # logging.info("Calling RPC Run: " + str(command))
                result = rpc.call_rpc(target_ip, port, "Run", command, log=log_output, timeout=timeout, priority=priority)
                
                # fail test if call_rpc returns CALLBACK
                if result == "CALLBACK":
                    self.fail(msg = 'call_rpc timeout to SimpleRemote')

                logging.debug(result)
                return result                    


    def _wait_for_rpc_callback(self, jobid, skt, host, port, log_output=True, timeout=1800, target_ip=None):
        if target_ip == None:
            target_ip = self.dut_ip

        skt.listen()
        if log_output:
            logging.debug ("Listening for " + str(timeout) + " seconds.")

        x = 0
        result = ""
        done = False
        client_socket = None
        while x <= int(timeout):
            readable, _, _ = select.select([skt], [], [], 1.0)
            if readable and skt in readable:
                client_socket, client_ip = skt.accept()
                if log_output:
                    logging.debug ("Accepted connection from " + str(client_ip))
                break
            x += 1
            if x >= int(timeout):
                return "CALLBACK"

        result = client_socket.recv(1024).decode()
        if client_socket:
            client_socket.close()
        if log_output:
            logging.debug ("Getting result for job " + str(jobid))
        job_result = self._get_job_result(int(jobid), log_output=log_output, target_ip=target_ip)

        return job_result

    def _get_job_result(self, jobid, port="", log_output=True, target_ip=""):
        if port == "":
            port = self.rpc_port
        if target_ip == "":
            target_ip = self.dut_ip
        result = rpc.get_job_result(target_ip, port, jobid, log=log_output)
        return result


    def _host_call(self, command, cwd=".", expected_exit_code="0", blocking=True, timeout=None, output=True):
        if (command == ""):
            logging.debug("host_call: command is blank.")
            return

        logging.debug("Calling: " + str(command))
        if blocking:
            threadComplete = threading.Event()
        else:
            threadComplete = None

        # Thread End Event
        endThreadEvent = threading.Event()
        hostCallException = threading.Event()

        # Spin a new thread to start and monitor new process (new thread prevents hard blocking in the case of rundown)
        hostCallThread = thread_with_exception("Host Call Thread", self.host_call_thread, args=(command, cwd, threadComplete, expected_exit_code, True, timeout, output), exceptionEvent=hostCallException, threadEvent=endThreadEvent)
        hostCallThread.daemon = True # Set thread to die with the program

        # Add to list of running threads
        self.activeHostCalls.append(hostCallThread)
        hostCallThread.start()

        if not blocking:
            # Remove from list of running threads
            self.activeHostCalls.remove(hostCallThread)
            return

        # Block on thread
        endThreadEvent.wait()

        hostCallThread.join()

        # Check if Exception occured in other thread (setting event means no exception was raised)
        if (hostCallException.is_set()):
            raise Exception("Exception raised in host call, see logs for details")

        out = hostCallThread.result
        
        # Remove from list of running threads
        self.activeHostCalls.remove(hostCallThread)

        return out
    
    def queue_output(self, output, queue):
        for line in iter(output.readline, b''):
            queue.put(line)
        output.close()

    def host_call_thread(self, command, cwd, threadComplete, expected_exit_code, shell=True, timeout=None, output=True):
        # Create a new process for the host call
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = shell, cwd = cwd)

        # Temporary array for result
        data_out = bytearray()
        data_err = bytearray()
        out = ""
        err = ""

        # Create queues for pulling back thread output
        out_queue = Queue()
        err_queue = Queue()

        # Non-Blocking Pipe Read Threads
        std_thread = threading.Thread(target=self.queue_output, args=(p.stdout, out_queue)) # Collect standard output 
        err_thread = threading.Thread(target=self.queue_output, args=(p.stderr, err_queue)) # Collect standard error
        
        # End threads with host process
        std_thread.daemon = True 
        err_thread.daemon = True 
        
        # Start the pipe threads
        std_thread.start()
        err_thread.start()

        # Get Start time for timeouts
        start_time = datetime.now()

        # Non-blocking wait for process return with timeout
        while (p.poll() is None or not out_queue.empty() or not err_queue.empty()) and (timeout is None or (float((datetime.now() - start_time).total_seconds()) <= float(timeout))):
            # Check if there is any output to read
            if out_queue.empty() and err_queue.empty():
                # Sleep between host call polls if no new output
                time.sleep(1)

            # Get any STDOUT data
            try:
                # Non-Blocking pipe read
                line_out = out_queue.get_nowait()

                # Log new lines
                if "winappdriver" not in command.lower() and "curl" not in command.lower():
                    if len(line_out) > 0:
                        for line in line_out.split(b'\n'):
                            try:
                                l = line.decode().strip("\r\n")
                                if l:
                                    out += l
                                    if output:
                                        logging.debug(l)
                            except:
                                pass
                
                # Add lines to output string
                data_out += line_out
            except Empty:
                pass
            
            # Get any STDERR data
            try:
                # Non-Blocking pipe read
                line_err = err_queue.get_nowait()

                # Log new lines
                if "winappdriver" not in command.lower() and "curl" not in command.lower():
                    if len(line_err) > 0:
                        for line in line_err.split(b'\n'):
                            try:
                                l = line.decode().strip("\r\n")
                                if l:
                                    err += l
                                    if output:
                                        logging.error(l)
                            except:
                                pass

                # Add lines to output string
                data_err += line_err
            except Empty:
                pass
        
        # Check if call timedout
        if timeout is not None:
            if float((datetime.now() - start_time).total_seconds()) > float(timeout):
                timeout_state = True
                raise Exception("Host call Timeout Reached!")

        # out = data_out
        # err = data_err

        actual_exit_code = str(p.returncode)

        # Verify expected exit code
        if(expected_exit_code != ""):
            if actual_exit_code != expected_exit_code :
                raise Exception('The call\'s exit code {0} doesn\'t match with expected exit code {1}'.format(actual_exit_code, expected_exit_code))
        
        # Decode result
        out = out.strip("\r\n")
        err = err.strip("\r\n")
        
        # Set thread end and return result
        if (threadComplete != None):
            threadComplete.set()
        return out + err


    def _remote_make_dir(self, path, delete=False):
        logging.debug("Making directory: " + path)
        if self.platform.lower() == "android":
            if delete:
                self._host_call("adb -s " + str(self.dut_ip) + ":5555 shell rm -r " + path, expected_exit_code="")
            self._host_call("adb -s " + str(self.dut_ip) + ":5555 shell mkdir " + path, expected_exit_code="")
        elif self.platform.lower() == "macos":
            if delete:
                self._call(["rm", "-rf " + path], callback=False, timeout=10)
            self._call(["mkdir", "-p " + path], callback=False, timeout=10)
        else:
            try:
                if delete:
                    self._call(["cmd.exe", '/c if exist ' + path + ' rmdir ' + path + ' /S /Q'], callback = False,  timeout = 10)                
                self._call(["cmd.exe", "/c if not exist " + path + " mkdir " + path ], callback = False, timeout = 10)
            except:
                logging.warning("Could not create remote directory: " + path)


    def _upload_json(self, source, dest):
        logging.debug("Uploading Json files from " + source + " to " + dest)
        if Params.get('global', 'local_execution') != '1' and self.platform.lower() != "android":
            folder = os.path.basename(source)
            full_dest = os.path.join(dest, folder)
            self._remote_make_dir(full_dest)
            rpc.upload(self.dut_ip, self.rpc_port, source+"\\*.json", full_dest)
        else:
            self._upload(source, dest)

    def _upload(self, source, dest, check_modified=True):
        if Params.get('global', 'local_execution') != '1':
            logging.debug("Uploading " + source + " to " + dest)
            if self.platform.lower() == "android":
                self._host_call("adb -s " + str(self.dut_ip) + ":5555 push " + source + " " + dest, expected_exit_code="")
            else:
                if os.path.isdir(source):
                    folder = os.path.basename(source)
                    full_dest = os.path.join(dest, folder)
                    if self.platform.lower() == "windows":
                        self._call(["cmd.exe", '/c if exist ' + full_dest + ' rmdir ' + full_dest + ' /S /Q'], callback = False)
                    elif self.platform.lower() == "macos":
                        full_dest = dest + "/" + folder
                        self._call(["rm", "-rf " + full_dest], callback=False)
                else:
                    if check_modified:
                        if self.platform.lower() == "windows":
                            # Check if file exists and is the same
                            dest_file = os.path.basename(source)
                            result = self._call(["cmd.exe", f'/c forfiles /P "{dest}" /M "{dest_file}" /C "cmd /c echo @fdate @ftime"'], expected_exit_code="")

                            logging.debug("RESULT: " + result)
                            if "not found" in result or "not exist" in result:
                                logging.info("Dest file doesn't exist, uploading: " + source)
                                rpc.upload(self.dut_ip, self.rpc_port, source, dest)
                                return
                            # Parse the result to get the modification time
                            lines = result.splitlines()
                            if len(lines) < 1:
                                logging.error("Could not parse modification time from result: " + result)
                                return
                            # Example line: "06/13/2024 03:30:11 PM"
                            time_pieces = lines[0].split()
                            result_time = None

                            # Existing parser path (US date + 12-hour time)
                            if len(time_pieces) >= 3:
                                mod_time_str = time_pieces[0] + " " + time_pieces[1] + " " + time_pieces[2]
                                logging.debug("Modification time string: " + mod_time_str)
                                try:
                                    result_time = datetime.strptime(mod_time_str, "%m/%d/%Y %I:%M:%S %p")
                                except Exception:
                                    result_time = None

                            # NOTE: This fallback change is done only to support MTL-SU-IDCLAB-23,
                            # where `forfiles` returns values like "08-03-2026 17:00:47".
                            if result_time is None and len(time_pieces) >= 2:
                                mod_time_str = time_pieces[0] + " " + time_pieces[1]
                                logging.debug("Fallback modification time string: " + mod_time_str)
                                for time_fmt in ("%d-%m-%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S"):
                                    try:
                                        result_time = datetime.strptime(mod_time_str, time_fmt)
                                        break
                                    except Exception:
                                        pass

                            if result_time is None:
                                logging.error("Could not parse modification time from result: " + lines[0])
                                return

                            logging.debug("Parsed modification time: " + str(result_time))
                            source_time = datetime.fromtimestamp(os.path.getmtime(source))
                            logging.debug("Source modification time: " + str(source_time))
                            if source_time <= result_time:
                                logging.debug("File not modified, skipping upload: " + source)
                                return
                        elif self.platform.lower() == "macos":
                            dest_file = dest + "/" + os.path.basename(source)
                            result = self._call(["stat", f'-f "%Sm" -t "%Y-%m-%d %H:%M:%S" "{dest_file}"'], expected_exit_code="")
                            logging.debug("RESULT: " + result)
                            if "stat" not in result:
                                # Convert the result string to a datetime object
                                if result.strip():
                                    try:
                                        # Example result: '2024-06-13 15:30:00'
                                        result_time = datetime.strptime(result.strip().replace('"', ''), "%Y-%m-%d %H:%M:%S")
                                        source_time = datetime.fromtimestamp(os.path.getmtime(source))
                                        if source_time <= result_time:
                                            logging.debug("File not modified, skipping upload: " + source)
                                            return
                                        else:
                                            rpc.upload(self.dut_ip, self.rpc_port, source, dest)
                                            self._call(["chmod", f'775 {dest_file}'])
                                            return
                                    except Exception as e:
                                        logging.warning(f"Could not parse modification time: {result}. Error: {e}")
                            else:
                                logging.debug("Dest file doesn't exist, uploading: " + source)
                                rpc.upload(self.dut_ip, self.rpc_port, source, dest)
                                self._call(["chmod", f'775 {dest_file}'])
                                return

                logging.debug("Dest file doesn't exist, uploading: " + source)
                rpc.upload(self.dut_ip, self.rpc_port, source, dest)
        else:
            # shutil.copy - copies single file.  If dest does not exist, will rename file to dest.  If dest is folder, then copy into dest.
            # shutil.copytree - recursively copies folder.  Dest folder must not exist.  Doesn't accept wildcards.
            if not os.path.isdir(dest):
                if os.path.exists(dest):
                    os.remove(dest)
                os.makedirs(dest)
            if os.path.isfile(source):
                logging.debug("Copying file: " + source + " to " + dest)
                shutil.copy(source, dest)
            elif os.path.isdir(source):
                logging.debug("Copying folder: " + source + " to " + dest)
                folder = os.path.basename(source)
                full_dest = os.path.join(dest, folder)
                try:
                    os.chmod(full_dest, stat.S_IWRITE)
                except:
                    pass
                shutil.rmtree(full_dest, ignore_errors=True)
                shutil.copytree(source, full_dest)
            else: # glob
                logging.debug("Copying glob: " + source + " to " + dest)
                for filename in glob.glob(source):
                    shutil.copy(filename, dest)

    def resolve(self, path):
        path = Path(path)
        for root in self.roots:
            candidate = root / path
            if candidate.exists():
                return str(candidate)
        raise FileNotFoundError(path)

    def _find_latest_training_folder(self, module = ""):
        # logging.info("starting to look for latest training folder")
        training_name = ""
        training_root = ""
        if (module == ""):
            module = Params.get('global', 'module_name')
        training_folder = module + "_training_???"
        # logging.debug("Finding training folder: Looking for " + training_folder)
        # dirpath = self.result_dir + "\\..\\Training\\"
        dirpath = Params.getCalculated("base_result_dir") + "\\Training"

        for root, dirs, files in os.walk(dirpath):
            for dir in dirs:
                # logging.debug("Finding training folder: Checking " + root + "\\" + dir)
                if glob.fnmatch.fnmatch(dir, training_folder):
                    training_name = dir
                    training_root = root

        # if training_name == "":
        #     dirpath = self.result_dir + "\\..\\..\\Training\\"
        #     training_root = ""
        #     for root, dirs, files in os.walk(dirpath):
        #         for dir in dirs:
        #             # logging.debug("Finding training folder: Checking " + root + "\\" + dir)
        #             if glob.fnmatch.fnmatch(dir, training_folder):
        #                 # logging.debug("Finding training folder: Found " + root + "\\" + dir)
        #                 training_name = dir
        #                 training_root = root
        self.training_path_host = os.path.join(training_root, training_name)
        logging.debug("found the training folder " + self.training_path_host)

        if not training_name:
            self._assert(f"Training run missing on the host")

        if not os.path.isfile(os.path.join(self.training_path_host, ".PASS")):
            self._assert(f"Most recent training run failed")

        return training_root, training_name



    def _copy_data_from_remote(self, dest, source=None, target_ip=None, single_file=False):
        if source is None:
            source = self.dut_data_path
        if target_ip == None:
            target_ip = self.dut_ip
        if self.platform.lower() == "android":
            try:
                self._host_call("adb -s " + str(target_ip) + ":5555 pull " + source + " " + dest, expected_exit_code="", timeout=300)
            except:
                logging.error("Copy Data from Remote: Host Call Timeout Reached! 300s - no return")
            return

        if Params.get('global', 'local_execution') !='1':
            
            logging.debug("Copying from " + source + " to " + dest)
            if self.platform.lower() == "windows" or self.platform.lower() == "w365":
                if self._check_remote_file_exists(source, target_ip = target_ip):
                    if not single_file:
                        if source == self.dut_data_path:
                            logging.debug("First Copy SimpleRemote log file to " + source)
                            source_path = "C:\\simple_remote_*.log"
                            self._call(["cmd.exe", '/c copy ' + source_path + ' ' + source], expected_exit_code="")
                        
                rpc.download(target_ip, self.rpc_port, source, dest)
            elif self.platform.lower() == "macos":
                rpc.download(target_ip, self.rpc_port, source, dest)

    ''' Checks if path exists on DUT '''
    def _check_remote_file_exists(self, path, in_exec_path=True, target_ip=None):
        if target_ip == None:
            target_ip = self.dut_ip
        if self.platform.lower() == "windows" or self.platform.lower() == "w365":
            if in_exec_path:
                # Strip leading path breaks before joining
                if path[:1] == "\\":
                    path = path[1:]
                path = os.path.join(self.dut_exec_path, path)
            file_name = self._call(["cmd.exe", "/c if exist " + path + " echo " + "File exists at location " + path], expected_exit_code="", target_ip=target_ip)
            # logging.info("Checking: '" + file_name + "'")
            if file_name == "":
                return False
        elif self.platform.lower() == "macos":
            if in_exec_path:
                # Strip leading path breaks before joining
                if path[:1] == "/":
                    path = path[1:]
                path = self.dut_exec_path + "/" + path
            file_name = self._call(["ls", path], expected_exit_code="", target_ip=target_ip)
            # logging.info("Checking: '" + file_name + "'")
            if "No such file or directory" in file_name:
                return False
        return True

    ''' Creates the prep status file if there is no error or failures. If exists, deletes first. '''
    def createPrepStatusControlFile(self, suffix=""):
        if isinstance(suffix, list):
            suffix = self._getLatestFileTimestampSuffix(suffix)
        path = os.path.join(self.dut_exec_path, "prep_status", self._module + suffix)
        if self.platform.lower() == "macos":
            path = path.replace("\\", "/")
        self._remote_make_dir(path, True)

    ''' Checks if preps in prep_list ran and if not add them to assert_list '''
    def checkPrepStatus(self, prep_list):
        assert_list = ""
        if not self.prep_status_enable:
            return assert_list
        for prep in prep_list:
            if self.platform.lower() == "macos":
                path = "prep_status/" + prep
            else:
                path = "prep_status\\" + prep
            if not self._check_remote_file_exists(path):
                assert_list += "Please run " + prep + " first\n"
        return assert_list

    def _getLatestFileTimestampSuffix(self, paths):
        latest = None

        for p in paths:
            path = Path(self.resolve(p))

            if not path.exists():
                continue

            if path.is_file():
                mtime = path.stat().st_mtime
                if latest is None or mtime > latest:
                    latest = mtime
            elif path.is_dir():
                for sub in path.rglob("*"):
                    if sub.is_file():
                        mtime = sub.stat().st_mtime
                        if latest is None or mtime > latest:
                            latest = mtime

        if latest:
            return f"_{datetime.fromtimestamp(latest).strftime('%Y%m%d_%H%M%S')}"
        else:
            return ""

    def checkPrepStatusNew(self, prep_list):
        prep_scenarios_to_run = []
        for prep in prep_list:
            if isinstance(prep, tuple):
                if isinstance(prep[1], list):
                    prep_str = f"{prep[0]}{self._getLatestFileTimestampSuffix(prep[1])}"
                else:
                    prep_str = f"{prep[0]}{prep[1]}"
            else:
                prep_str = prep
            if not self._check_remote_file_exists("prep_status\\" + prep_str):
                prep_scenarios_to_run.append(prep)
        return prep_scenarios_to_run

    ''' Checks if parameters are valid '''
    def prepCheck(self):
        if not Params.checkParams:
            self._assert("Invalid parameters are specified")

    ''' Checking common settings are available to run tests '''
    def prepCheckCommon(self):
        assert_list = ""
        hostname = "microsoft.com"
        response = os.system("ping -c 1" + hostname)
        if response != 1 :
            assert_list += "There is no network connection\n"
        
        # Check if WinApp Driver is available
        if not self._check_remote_file_exists("WindowsApplicationDriver\\WinAppDriver.exe"):
            assert_list += "WinApp Driver is missing on DUT \n"
        
        # Check parameters are set
        if self.dut_ip == '':
            assert_list += "Dut ip information is missing in settings file \n"
        if self.platform == '':
            assert_list += "Platform information is missing in settings file \n"

        if assert_list != "":
            self._assert(assert_list)


    ''' Checks specified artifact package exists in specified path on host, if not download to specified path '''
    def _check_and_download(self, name, path, url=""):
        target = path + "\\" + name
        lock = target + ".lock"
        logging.info("Trying to acquire lock: " + lock)
        for count in range(1000):
            try:
                os.makedirs(lock)
                logging.info("Lock acquired")
                break
            except:
                time.sleep(5)
        if count >= 1000:
            raise Exception("Timeout trying to acquire lock: " + lock)

        # Check if resource already exists and download if not
        try:
            if not os.path.exists(target):
                logging.info("Downloading resource: " + name)
                command = '"c:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd" artifacts universal download --organization https://msftdevicespartners.visualstudio.com/ --project="Power" --scope project --feed hobl_resources --name ' + name + ' --version * --path ' + target
                if url == "": # assume artifact
                    result = self._host_call(command, expected_exit_code="", output=False)
                    logging.debug("az call output: " + result)
                    if "run the login command" in result:
                        logging.info("Follow instructions in browser to login to Azure...")
                        result = self._host_call('"c:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd" login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47 --allow-no-subscriptions > nul', expected_exit_code="", output=False)
                        logging.debug("az login output: " + result)
                        result = self._host_call(command, expected_exit_code="", output=False)
                        logging.debug("2nd az call output: " + result)
                    if "Personal Access Token used has expired" in result:
                        logging.error("The host computer is using an expired Personal Access Token for https://msftdevicespartners.visualstudio.com.  Please regenerate and try again.")
                        # os.rmdir(lock)
                        raise Exception("The host computer is using an expired Personal Access Token for https://msftdevicespartners.visualstudio.com.  Please regenerate and try again.")
                    elif "You are not authorized" in result:
                        logging.error("The Personal Access Token being used for https://msftdevicespartners.visualstudio.com is not authorized to access the specified resource.  Please edit the PAT to make sure the 'Packaging' Read scope is selected.")
                        # os.rmdir(lock)
                        raise Exception("The Personal Access Token being used for https://msftdevicespartners.visualstudio.com is not authorized to access the specified resource.  Please edit the PAT to make sure the 'Packaging' Read scope is selected.")
                    elif "Cannot find the package" in result:
                        logging.error("The specified package cannot be found.")
                        # os.rmdir(lock)
                        raise Exception("The specified package cannot be found.")
                    elif "system cannot find the path" in result:
                        logging.error("Azure CLI is not installed.  Please run host_setup to install it.")
                        # os.rmdir(lock)
                        raise Exception("The specified package cannot be found.")
                    elif "ERROR" in result:
                        # os.rmdir(lock)
                        raise Exception("Error downloading artifact.")
             
                else:
                    with requests.get(url, stream=True) as r:
                        with open(target, 'wb') as f:
                            shutil.copyfileobj(r.raw, f)
            else:
                logging.info("Resource " + name + " already exists")
        except Exception as e:
            logging.info("Releasing lock")
            os.rmdir(lock)
            raise e

        # Release lock
        logging.info("Releasing lock")
        os.rmdir(lock)


    def kill_wrapper(self):
        try:
            logging.debug("Calling scenarios kill method")
            result = self.kill()
            if result == 0:
                return
        except:
            pass
        finally:
            self.toolCallBacks("cleanup", fail_pass=True)

        if self.platform.lower() == "windows":
            # Just to be sure these common processes don't get left running.
            try:
                logging.debug("Cancelling trace")
                self._call(["cmd.exe", "/c wpr.exe -cancel > null 2>&1"], expected_exit_code="")
            except:
                pass
            try:
                logging.debug("Killing ffmpeg")
                self._call(["cmd.exe", '/c taskkill /IM ffmpeg.exe /T /F > null 2>&1'], expected_exit_code="")
            except:
                pass
            # try:
            #     logging.debug("Killing batterybar")
            #     self._call(["cmd.exe", '/c taskkill /IM batterybar.exe /T /F > null 2>&1'], expected_exit_code="")
            # except:
            #     pass
            # try:
            #     if Params.get('global', 'dut_ip') != '127.0.0.1':
            #         logging.debug("Killing cmd")
            #         self._call(["cmd.exe", '/c taskkill /IM cmd.exe /T /F > null 2>&1'], expected_exit_code="")
            # except:
            #     pass
            try:
                logging.debug("Killing monitorPowerEvents.exe")
                self._call(["cmd.exe", '/c taskkill /IM MonitorPowerEvents.exe /T /F > null 2>&1'], expected_exit_code="")
            except:
                pass

    def _kill(self, names, force = True, timeout = 30):
        name_list = names if isinstance(names, list) else names.split()
        for name in name_list:
            logging.debug('killing application: ' + name)
            tasks = ""
            # self._call(["cmd.exe", "/C taskkill /F /T /IM " + name])
            if self.platform.lower() == 'wcos':
                # TODO:Temporary Fix - Recheck with LKG
                tasks = self._call(["cmd.exe", '/c kill -f ' + str(name)], expected_exit_code="")
            elif self.platform.lower() == 'android':
                pass
            elif self.platform.lower() == 'macos':
                tasks = self._call(["killall", name], expected_exit_code="", timeout=timeout)
            else:
                tasks = self._call(["cmd.exe", '/c tasklist /nh /fo csv /fi "IMAGENAME eq ' + name + '"'], expected_exit_code="", timeout=timeout)
                # print tasks
                # output = json.loads(tasks)
                # tasks = output["result"]
                task_set = set()

                if 'INFO: No tasks' not in tasks:
                    for task in tasks.split("\n"):
                        task_name = task.split(",")[0]
                        task_set.add(task_name.strip('"').strip())
                    for task_name in task_set:
                        if task_name == "":
                            continue
                        logging.debug("Force Killing: " + task_name)
                        if task_name == "cmd.exe":
                            if Params.get('global', 'dut_ip') != '127.0.0.1':
                                self._call(["cmd.exe", '/c taskkill /f /T /IM ' + str(task_name) + " > null 2>&1"], expected_exit_code="", timeout=timeout)
                        else:
                            if (force):
                                self._call(["cmd.exe", '/c taskkill /f /T /IM ' + str(task_name)], expected_exit_code="", timeout=timeout)
                            else:
                                self._call(["cmd.exe", '/c taskkill /IM ' + str(task_name)], expected_exit_code="", timeout=timeout)

    def _host_kill(self, names):
        name_list = names if isinstance(names, list) else names.split()
        for name in name_list:
            logging.debug('killing application: ' + name)
            tasks = self._host_call("cmd.exe" + ' /c tasklist /nh /fo csv /fi "IMAGENAME eq ' + name + '"')
            # print tasks
            # output = json.loads(tasks)
            # tasks = output["result"]
            task_set = set()

            if 'INFO: No tasks' not in tasks:
                for task in tasks.split("\n"):
                    task_name = task.split(",")[0]
                    task_set.add(task_name.strip('"'))
                for task_name in task_set:
                    if task_name == "":
                        continue
                    logging.debug("Force Killing: " + task_name)
                    if task_name == "cmd.exe":
                        self._host_call("cmd.exe" + ' /c taskkill /f /T /IM ' + str(task_name) + " > null 2>&1", expected_exit_code="")
                    else:
                        self._host_call("cmd.exe" + ' /c taskkill /f /T /IM ' + str(task_name))


    def _page_source(self, driver, name = ""):
        source = driver.page_source
        if name == "":
            name = self.testname + "_source"
        filename = self.result_dir + "\\" + name + ".xml"
        fh = io.open(filename, 'w', encoding='utf-8')
        fh.write(source)
        fh.close()


    def _screenshot(self, name = ""):
        if name == "":
            name = os.path.join(self.result_dir, "screenshot.png")
        if self.platform.lower() == 'android':
            name = self.dut_data_path + '/screenshots/' + name
        else:
            name = os.path.join(self.result_dir, name)

        # Try to create /screenshots
        # logging.info("Creating " + self.dut_data_path + "/screenshots")
        if self.platform.lower() == 'android':
            self._host_call("adb -s " + self.dut_ip + ":5555 shell mkdir " + self.dut_data_path + "/screenshots")

        logging.info("Saving screenshot: " + name)
        if self.platform.lower() == 'android':
            self._host_call("adb -s " + self.dut_ip + ":5555 shell screencap " + name)
        # elif self.platform.lower() == 'windows':
        # I believe windows and mac use same method.
        else:
            img = self._capture_screen()
            rgb_image = cv.cvtColor(img, cv.COLOR_BGR2RGB)
            Image.fromarray(rgb_image).save(name)


            # screenshot_path = os.path.join(self.dut_exec_path, "ScreenShot.exe")
            # screenshot_path_old = os.path.join(self.dut_exec_path, "ScreenCapture.exe")
            # if self._check_remote_file_exists(screenshot_path):
            #     self._call([os.path.join(self.dut_exec_path, "ScreenShot.exe"), name])
            # elif self._check_remote_file_exists(screenshot_path_old):
            #     logging.info("screenshot.exe doesn't exists. Trying old screenshot method.")
            #     self._call([os.path.join(self.dut_exec_path, "ScreenCapture.exe"), name])
            # else:
            #     logging.info("No Screenshots avaliable")
        # elif self.platform.lower() == 'macos':
        #     # TODO: Implement MacOS screenshot
        #     img = self._capture_screen()
        #     rgb_image = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        #     Image.fromarray(rgb_image).save(name)
        #     pass
    
    # ############################################################################################################
    # Template Matching Functions ################################################################################
    # ############################################################################################################
    # Template matching global vars
    default_threshold = 0.70                        # Threshold for template matching
    default_scale = [1.0]                           # Scale factors to check with the template              # Scale factors to check with the template
    default_template_method = cv.TM_SQDIFF_NORMED   # Template matching method
    edge_detect = True                              # Enable edge detection
    edge_detect_thresholds = [5, 30]                # Thresholds for edge detection
    edge_blur = True                                # Enable edge blur
    edge_blur_kernel = 7                            # Kernel size for edge blur, changes the amount of blur applied
    upscale = 1.0                                   # Upscale the template and screenshot by this factor
    template_edge_crop = True                       # Crop the edges of the template in to give space for the blur in the screenshot. Prevents lower scores when edges are close but outside the template area
    template_edge_crop_amount = 5                   # Amount of pixels to crop from the edges of the template. This may need to be adjusted based on the blur kernel size
    standardize_dpi = True                         # Standardize the DPI of the template to 96dpi for 100% Windows scaling
    json_parent_dir = ""                            # Directory where the json file and all the images are stored
    output_images = False                            # Output images for debugging. Saved to the results directory
    dialation = True                                # Apply dialation to the screenshot and template after edge detection and before blur
    dialation_kernel = (3,3)                        # Dialation kernel size

    # Get the point of the template in the screenshot
    def _get_point_by_template(self, template, screenshot=None, threshold=None, method=default_template_method, scale_factors=default_scale, offsets=(0.5, 0.5), edge_detect_thresholds=[]):
        # Check if the threshold is provided
        if threshold is None:
            threshold = self.default_threshold
        
        if edge_detect_thresholds == []:
            edge_detect_thresholds = self.edge_detect_thresholds
        logging.debug(f"Using edge detect thresholds: {edge_detect_thresholds}")

        # Load the screenshot in opencv
        if screenshot is None:
            # Capture the screen if no screenshot is provided
            screen_img = self._capture_screen()
            assert False # TODO: Just making sure we don't go here for now.
        elif isinstance(screenshot, str):
            # Load the screenshot from a file if a string is provided
            screen_img = cv.imread(os.path.join(self.json_parent_dir, str(screenshot)), cv.IMREAD_GRAYSCALE)
            assert False # TODO: Just making sure we don't go here for now.
        else:
            # Use the provided screenshot if it is a numpy array already
            screen_img = copy.deepcopy(screenshot)
        screen_img = cv.cvtColor(screen_img, cv.COLOR_BGR2GRAY)

        if self.upscale != 1.0:
            screen_img = cv.resize(screen_img, (int(screen_img.shape[1] * (self.upscale)), int(screen_img.shape[0] * (self.upscale))), interpolation= cv.INTER_LINEAR)

        screen_gray_img = screen_img

        # Load the recorded template in opencv
        if isinstance(template, str):
            # logging.debug("Loading template: " + str(template))
            # Load the template from a file if a string is provided
            template_img = cv.imread(os.path.join(self.json_parent_dir, template))
            template_img = cv.cvtColor(template_img, cv.COLOR_BGR2GRAY)
        else:
            # Use the provided template if it is a numpy array already
            raise Exception("Template must be file path in order to read dpi! Unable to use preloaded template.")
            template_img = template

        # Check if the template and screenshot are valid and that the template is smaller than the screenshot
        assert template_img is not None, "Template not found"
        assert screen_img is not None, "Screenshot not found"

        if self.upscale != 1.0:
            start_time = datetime.now()
            template_img = cv.resize(template_img, (int(template_img.shape[1] * (self.upscale)), int(template_img.shape[0] * (self.upscale))), interpolation= cv.INTER_LINEAR)
            # logging.debug(f"Template upscale took: {(datetime.now() - start_time).total_seconds()}")

        if self.standardize_dpi:
            start_time = datetime.now()
            # Adjust the scale of the template to match the device Windows scaling
            template_dpi = int(Image.open(os.path.join(self.json_parent_dir, template)).info['dpi'][0])
            factor = round(template_dpi / 24)
            template_dpi = factor * 24
            device_dpi = int(self._get_screen_scale(self.current_screen) * 96)
            if (self.dut_scaling_override != ""):
                device_dpi = int(float(self.dut_scaling_override) * 96)
                logging.debug(f"Overrideing DUT DPI to: {device_dpi}")
            logging.debug(f"DPI - Template: {template_dpi}, Device: {device_dpi}")
            # logging.info(f"Screen res before: {screen_img.shape[1]} x {screen_img.shape[0]}")
            # logging.info(f"template res before: {template_img.shape[1]} x {template_img.shape[0]}")
            if template_dpi > device_dpi:
                scale_factor = template_dpi / device_dpi
                logging.debug(f"Scaling screen capture by {scale_factor:.2f} to match template DPI")
                screen_img = cv.resize(screen_img, (int(screen_img.shape[1] * scale_factor), int(screen_img.shape[0] * scale_factor)), interpolation= cv.INTER_LINEAR)
            elif template_dpi < device_dpi:
                scale_factor = device_dpi / template_dpi
                logging.debug(f"Scaling template by {scale_factor:.2f} to match device DPI")
                template_img = cv.resize(template_img, (int(template_img.shape[1] * scale_factor), int(template_img.shape[0] * scale_factor)), interpolation= cv.INTER_LINEAR)
            else:
                # They are the same DPI and no need to resize
                pass
            # logging.info(f"Screen res after: {screen_img.shape[1]} x {screen_img.shape[0]}")
            # logging.info(f"template res after: {template_img.shape[1]} x {template_img.shape[0]}")

            template_resize_img = template_img
            # logging.debug(f"Template DPI standardization took: {(datetime.now() - start_time).total_seconds()}")

        if self.edge_blur:
            start_time = datetime.now()
            screen_img = cv.GaussianBlur(screen_img,(3, 3),0)
            # logging.debug(f"Screen blur took: {(datetime.now() - start_time).total_seconds()}")

        # Adjust the screenshot (outside of loop to avoid multiple adjustments)
        if self.edge_detect:
            start_time = datetime.now()
            screen_img = cv.Canny(screen_img, edge_detect_thresholds[0], edge_detect_thresholds[1])
            screen_edge_img = screen_img
            # logging.debug(f"Screen edge detection took: {(datetime.now() - start_time).total_seconds()}")

        # Apply dilation
        if self.dialation:
            start_time = datetime.now()
            kernel = cv.getStructuringElement(cv.MORPH_RECT, self.dialation_kernel)
            screen_img = cv.dilate(screen_img, kernel, iterations=1)
            # logging.debug(f"Screen dialation took: {(datetime.now() - start_time).total_seconds()}")

        if self.edge_blur:
            start_time = datetime.now()
            screen_img = cv.GaussianBlur(screen_img,( self.edge_blur_kernel, self.edge_blur_kernel),0)
            # logging.debug(f"Screen blur took: {(datetime.now() - start_time).total_seconds()}")

        # Make sure the scale factors are in a list even if only one is provided
        if not isinstance(scale_factors, list):
            scale_factors = [scale_factors]

        best_match = (False, 0)
        next_best_match_val = 0
        # Loop through the scaled templates and find the best match
        for scale in scale_factors:
            resized_template = imutils.resize(template_img, width=int(template_img.shape[1] * scale))
            h_screen = screen_img.shape[0]
            w_screen = screen_img.shape[1]
            h_template = int(template_img.shape[0] * scale)
            w_template = int(template_img.shape[1] * scale)
            # if (screen_img.shape[0] < int(template_img.shape[0] * scale)) or (screen_img.shape[1] < int(template_img.shape[1] * scale)):
            if (h_screen < h_template) or (w_screen < w_template):
                # Skip loop, template is larger than screenshot
                continue

            # Crop the edges of the template
            if self.template_edge_crop:
                resized_template = resized_template[self.template_edge_crop_amount:-self.template_edge_crop_amount, self.template_edge_crop_amount:-self.template_edge_crop_amount]
                h_template -= (self.template_edge_crop_amount * 2)
                w_template -= (self.template_edge_crop_amount * 2)

            # Convert the offsets to pixel values in the template
            # logging.debug(f"Original click point: {offsets}")
            pixel_offsets = (float(offsets[0]) * resized_template.shape[1], float(offsets[1]) * resized_template.shape[0])

            # Blur Edge detection images
            if self.edge_blur:
                start_time = datetime.now()
                resized_template = cv.GaussianBlur(resized_template, (3, 3), 0)
                # logging.debug(f"Template blur took: {(datetime.now() - start_time).total_seconds()}")

            # Edge detection
            if self.edge_detect:
                start_time = datetime.now()
                resized_template = cv.Canny(resized_template, edge_detect_thresholds[0], edge_detect_thresholds[1])
                resized_edge_template = resized_template
                # logging.debug(f"Template dge detection took: {(datetime.now() - start_time).total_seconds()}")

            # Apply dilation
            if self.dialation:
                start_time = datetime.now()
                kernel = cv.getStructuringElement(cv.MORPH_RECT, self.dialation_kernel)
                resized_template = cv.dilate(resized_template, kernel, iterations=1)
                # logging.debug(f"Template dialation took: {(datetime.now() - start_time).total_seconds()}")

            # Blur Edge detection images
            if self.edge_blur:
                start_time = datetime.now()
                resized_template = cv.GaussianBlur(resized_template, (self.edge_blur_kernel, self.edge_blur_kernel), 0)
                # logging.debug(f"Template blur took: {(datetime.now() - start_time).total_seconds()}")

            if self.output_images:
                template_basename = os.path.basename(template)
                # self._save_screen("resized_template_" + "_scale_" + str(scale) + str(template_basename), template_resize_img)
                self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
                # self._save_screen("scaled_edge_template_" + "_scale_" + str(scale) + str(template_basename), resized_edge_template)
                # self._save_screen("screen_gray_img_for_matching_with_" + str(template_basename), screen_gray_img)
                self._save_screen("capture_img_" + str(template_basename), screen_img)
                # self._save_screen("screen_edge_img_for_matching_with_" + str(template_basename), screen_edge_img)

            # Apply template matching
            start_time = datetime.now()
            result = cv.matchTemplate(screen_img, resized_template, method)
            # min_match_val, max_match_val, min_location, max_location = cv.minMaxLoc(result)

            # Determine the top 2 matches (best and 2nd best)
            num_matches = 2
            min_location = [0] * num_matches
            min_val = [0.0] * num_matches
            for i in range(num_matches):
                min_val[i], max_val, min_location[i], max_location = cv.minMaxLoc(result)
                val = result[min_location[i][1], min_location[i][0]]
                # Set the matched template area in the result matrix to worst value (1.0), so that it won't be considered in the next loop
                y_end = min(h_screen, min_location[i][1]+h_template//2+1)
                x_end = min(w_screen, min_location[i][0]+w_template//2+1)
                y_start = max(0, min_location[i][1]-h_template//2)
                x_start = max(0, min_location[i][0]-w_template//2)
                result[y_start:y_end, x_start:x_end] = 1.0
            # logging.debug(f"Matching took: {(datetime.now() - start_time).total_seconds()}")

            # Calculate the click point
            if template_dpi > device_dpi:
                # Adjust click point if screen shot is scaled up as thats not the same click point as the device's current scale factor
                point = int((min_location[0][0] + pixel_offsets[0]) / self.upscale / scale_factor), int((min_location[0][1] + pixel_offsets[1]) / self.upscale / scale_factor)
            else:
                point = int((min_location[0][0] + pixel_offsets[0]) / self.upscale), int((min_location[0][1] + pixel_offsets[1]) / self.upscale)
            logging.debug(f"Matched template: {template} at scale: {scale} confidence: {(1 - min_val[0])}")
            # logging.debug(f"Click point: {point}")

            # Save the new best match
            if (1 - min_val[1]) > next_best_match_val:
                next_best_match_val = 1 - min_val[1]
            if (1 - min_val[0]) > best_match[1]:
                best_match = (point, (1 - min_val[0]), next_best_match_val)
                # logging.info(best_match, str(scale))
            
        logging.debug(f"Best Match: {best_match}")
        # Check if the match is above the threshold
        if best_match[1] < threshold:
            # logging.warning("Best match below threshold!")
            logging.debug(f"Match: {best_match[1]}, below threshold: {threshold}")
            template_basename = os.path.basename(template)
            self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
            self._save_screen("capture_img_" + str(template_basename), screen_img)
            return  (False, best_match[1], next_best_match_val)

        # Uncomment below for debugging
        template_basename = os.path.basename(template)
        self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
        self._save_screen("capture_img_" + str(template_basename), screen_img)

        # return the click point and the confidence of the match
        return best_match

    # Capture a region of the screen and return it. Optionally save the image to a file as well
    def _capture_screen(self, filename=None, x=0, y=0, w=1, h=1):
        # If the filename is a list, then grab the first element as the filename
        if isinstance(filename, list):
            filename = filename[0]

        # logging.debug("Capturing screen: x=" + str(x) + ", y=" + str(y) + ", w=" + str(w) + ", h=" + str(h))
        screen_data = rpc.plugin_screenshot(self.dut_ip, self.rpc_port, "InputInject", x, y, w, h, self.current_screen)
        img = qoi.decode(screen_data)

        # return (img[:, :, ::-1].copy()) # Convert array format for opencv
        rgb_image = cv.cvtColor(img, cv.COLOR_RGB2BGR)

        # Save the image if a filename is provided
        if filename is not None:
            self._save_screen(os.path.basename(str(filename)), rgb_image)
            # save_path = os.path.join(str(self.result_dir), os.path.basename(str(filename)))
            # logging.debug("Saving screenshot: " + str(save_path))
            # Image.fromarray(img).save(save_path)
            
        return rgb_image
    
    # Save an image from the return of _capture_screen
    def _save_screen(self, filename, img):
        save_folder = os.path.join(self.result_dir, "image_matching")
        os.makedirs(save_folder, exist_ok=True)
        save_path = os.path.join(save_folder, filename)
        if len(img.shape) == 3: # Has 3 elements for color images, only 2 for grayscale.
            rgb_image = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        else:
            # Don't try to convert grayscale images
            rgb_image = img
        Image.fromarray(rgb_image).save(save_path) # Convert for PIL


    def _click_by_template(self, template, id=None, capture_id=None, threshold=None, method=default_template_method, scale=default_scale, primary=True, delay=100, x=0.5, y=0.5, edge_detect_thresholds=[], traceId=None, traceX=None, traceY=None, traceW=None, traceH=None, traceMs=None, traceFramerate=None):
        # Get the screenshot from the capture_id
        if capture_id is not None:
            screenshot = self.captures[capture_id]

        # Find the best point from the template or templates
        if len(template) == 0:
            raise Exception("Template not found")
        else:
            max_confidence = 0
            best_point = None
            for t in template:
                point, confidence, fail_level = self._get_point_by_template(t, screenshot, threshold, method, scale, offsets=(x, y), edge_detect_thresholds=edge_detect_thresholds)
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_point = point
            point = best_point
            logging.info(f"Confidence: {max_confidence:.2f}, Next match: {fail_level:.2f}")

        if point == False or point == None:
            # Did not find the template
            return False

        # Adjust the point in case the screenshot was cropped in
        x_adj = 0
        y_adj = 0
        if capture_id is not None:
            cap_action = self.get_action_by_id(capture_id)
            screen_width, screen_height = self._get_screen_size(self.current_screen)
            x_adj = int(float(cap_action["x"]) * screen_width)
            y_adj = int(float(cap_action["y"]) * screen_height)

        # Click the point
        x = (point[0] + x_adj) * self.dut_coord_scaler
        y = (point[1] + y_adj) * self.dut_coord_scaler
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Tap", int(x), int(y), delay, primary, self.current_screen, traceId, traceX, traceY, traceW, traceH, traceMs, traceFramerate)
        # time.sleep(sleep/1000) # Sleep is handled by the plugin
        # return the point for use or recording
        return point
    
    def _move_by_template(self, template, capture_id=None, threshold=None, method=default_template_method, scale=default_scale, delay=100, x=0.5, y=0.5, edge_detect_thresholds=[]):
        # Get the screenshot from the capture_id
        if capture_id is not None:
            screenshot = self.captures[capture_id]

        # Find the best point from the template or templates
        if len(template) == 0:
            raise Exception("Template not found")
        else:
            max_confidence = 0
            best_point = None
            for t in template:
                point, confidence, fail_level = self._get_point_by_template(t, screenshot, threshold, method, scale, offsets=(x, y), edge_detect_thresholds=edge_detect_thresholds)
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_point = point
            point = best_point

        if point == False:
            # Did not find the template
            return False

        # Adjust the point in case the screenshot was cropped in
        x_adj = 0
        y_adj = 0
        if capture_id is not None:
            screen_width, screen_height = self._get_screen_size(self.current_screen)
            x_adj = int(float(self.get_action_by_id(capture_id)["x"]) * screen_width)
            y_adj = int(float(self.get_action_by_id(capture_id)["y"]) * screen_height)


        # Move to the point
        x = (point[0] + x_adj) * self.dut_coord_scaler
        y = (point[1] + y_adj) * self.dut_coord_scaler
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "MoveTo", int(x), int(y), self.current_screen)
        # return the point for use or recording
        return point
    
    # TODO: Pipe in the typing speed
    # Send typing to the DUT
    def _send_text(self, text, typing_delay=None, traceId=None, traceX=None, traceY=None, traceW=None, traceH=None, traceMs=None, traceFramerate=None):
        # Get the typing delay from the class if it is not provided
        typing_delay = self.typing_delay if typing_delay is None else typing_delay
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", text, typing_delay, traceId, traceX, traceY, traceW, traceH, traceMs, traceFramerate)

    def _send_window_move(self, typing_delay, screen):
        typing_delay = self.typing_delay if typing_delay is None else typing_delay
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "WindowMove", typing_delay, screen)

    def _send_window_maximize(self):
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "WindowMaximize")

    def _scroll(self, x_frac, y_frac, direction, traceId=None, traceX=None, traceY=None, traceW=None, traceH=None, traceMs=None, traceFramerate=None):
        w_screen, h_screen = self._get_screen_size(self.current_screen)
        x = w_screen * x_frac * self.dut_coord_scaler
        y = h_screen * y_frac * self.dut_coord_scaler
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Scroll", int(x), int(y), 720, direction, self.current_screen, traceId, traceX, traceY, traceW, traceH, traceMs, traceFramerate)

    # Check for a template match in a screenshot. Returns True if the template is found, False if it is not
    def _check_by_template(self, template, capture_id=None, threshold=None, method=default_template_method, scale=default_scale, edge_detect_thresholds=[]):
        # Get the screenshot from the capture_id
        if capture_id is not None:
            screenshot = self.captures[capture_id]

        if len(template) == 0:
            raise Exception("Template not found")
        else:
            for t in template:
                point, confidence, fail_level = self._get_point_by_template(t, screenshot, threshold, method, scale, edge_detect_thresholds=edge_detect_thresholds)
                if point != False:
                    return True
            return False

    # Get the screen size, only check the first time it is called
    screen_width = [None] * MAX_SCREENS
    screen_height = [None] * MAX_SCREENS
    screen_scale = [None] * MAX_SCREENS
    def _get_screen_size(self, screen_index=0):
        if self.screen_width[screen_index] is None or self.screen_height[screen_index] is None or self.screen_scale[screen_index] is None:
            # self.screen_width, self.screen_height, self.screen_scale = rpc.plugin_screen_info(self.dut_ip, self.rpc_port, "InputInject")
            # logging.debug("Screen Size: " + str(self.screen_width) + "x" + str(self.screen_height) + ", Scale: " + str(self.screen_scale))

            screen_info = rpc.plugin_screen_info(self.dut_ip, self.rpc_port, "InputInject")
            for screen_index in range(len(screen_info)):
                self.screen_width[screen_index], self.screen_height[screen_index], self.screen_scale[screen_index] = screen_info[screen_index]
                logging.info(f"DUT screen {screen_index} size {self.screen_width[screen_index]} x {self.screen_height[screen_index]} @ scale {self.screen_scale[screen_index]}.")

        return self.screen_width[screen_index], self.screen_height[screen_index]
    
    # Wrapper to get the screen scale
    # Calls _get_screen_size if the screen scale is not set
    def _get_screen_scale(self, screen_index=0):
        if self.screen_scale[screen_index] is None:
            self._get_screen_size(screen_index)
        # logging.debug("Screen Scale: " + str(self.screen_scale))
        return self.screen_scale[screen_index]


    # Get the best scale factor for the template
    # Check the template against the screenshot at different scale factors
    def _set_scale_factor_by_template(self, template, screenshot=None, scale_factors=default_scale):
        best_match = 0
        best_scale = 1.0
        logging.info("Checking for best scale factor with template: " + str(template))
        for scale in scale_factors:
            point, confidence, fail_level = self._get_point_by_template(template, screenshot, scale_factors=scale)
            logging.debug("Scale: " + str(scale) + ", Confidence: " + str(confidence))
            if confidence > best_match:
                best_match = confidence
                best_scale = scale
        logging.info("Setting default scale factor to: " + str(best_scale))
        self.default_scale = [best_scale]
        return best_scale   # Return the best scale factor based on the template match

# ############################################################################################################
# Json Logic Control #########################################################################################
# ############################################################################################################
    ### Class Vars ###
    action_json = [] # Current json list of actions to process
    # last_action = None # Last action that was processed
    # last_action_result = 0 # Result of the last action, 0 for success, 1 for failure
    # in_failure_case = 0 # Flag to indicate if we are in an exception block and need to skip the else block
    captures = {} # Dictionary to store captured screenshots. Prevents needing to read from disk multiple times
    # action_index = 0

    # DEPRECATED
    # Get the next action to process
    # Returns the next action to process or 0 if there are no more actions to process
    # Returns 1 if the last action failed and there is no catch block to go to
    # def get_next_action(self):
    #     # If this is the first action, return the first action
    #     if self.last_action is None:
    #         # Log the screen scale for the first action so that we know what the scale is
    #         logging.info("Processing first action, device Screen Scale: " + str(self._get_screen_scale()))
    #         action = self.action_json[0]
    #         self.action_index += 1
        
    #     # This is not the first action, get the next action
    #     else:        
    #         # If there are no more actions to process, return 0. If the last action failed, raise an exception
    #         if self.action_index >= len(self.action_json):
    #             if self.last_action_result == 1:
    #                 raise Exception("Last Action Failed: " + str(self.last_action["id"]))
    #             return 0
            
    #         # If the last action failed, set the flag to indicate we are in an exception block and try to catch it in the next exception block
    #         elif self.last_action_result == 1:
    #             self.in_failure_case = 1 # Set the exception flag, we are in an exception case and need to handle it
    #             # If there is no exception block to go to, raise an exception to stop the test
    #             if self._find_next_type("Except", self.action_json[self.action_json.index(self.last_action):]) is None:
    #                 logging.error("No exception block found for failed action: " + str(self.last_action["id"]))
    #                 raise Exception("Unhandled Exception, failed action: " + str(self.last_action["id"]))
    #             # Get the next exception block
    #             action = self.action_json[self.action_json.index(self._find_next_type("Except", self.action_json[self.action_json.index(self.last_action):]))]
            
    #         else:
    #             # The last action succeeded, get the next action
    #             action = self.action_json[self.action_index]
    #             self.action_index += 1

    #     # Keep getting the next action until we find an action that is not a try, except, else, or end block or an import
    #     while(action["type"] == "Try" or action["type"] == "Except" or action["type"] == "Else" or action["type"] == "End" or action["type"] == "Include"):
    #         logging.debug("Skipping block: " + action["type"])
    #         # The next action is for a try case
    #         # Get the first action in the try case
    #         if action["type"] == "Try" or action["type"] == "Include":
    #             action = self.action_json[self.action_json.index(action) + 1]

    #         # The next action is for an exception case
    #         # We didn't fail the last action so we can skip the exception case
    #         if action["type"] == "Except" and self.in_failure_case == 0:
    #             logging.debug("Skipping exception block")
    #             action = self._find_next_type("Else", self.action_json[self.action_json.index(action):])
    #         # We did fail a previous action so we need to handle the exception case
    #         elif action["type"] == "Except" and self.in_failure_case == 1:
    #             logging.debug("Executing exception block")
    #             action = self.action_json[self.action_json.index(action) + 1]
            
    #         # The next action is for an else case
    #         # We didn't have any exceptions so we can run the else case
    #         if action["type"] == "Else" and self.in_failure_case == 0:
    #             logging.debug("Executing else block")
    #             action = self.action_json[self.action_json.index(action) + 1]
    #         # We did have an exception so we need to skip the else case
    #         elif action["type"] == "Else" and self.in_failure_case == 1:
    #             logging.debug("Skipping else block")
    #             action = self._find_next_type("End", self.action_json[self.action_json.index(action):])
            
    #         # Reached the end of the exception block
    #         if action["type"] == "End":
    #             logging.debug("End of exception block")
    #             # Reset the exception flag, exception has been handled
    #             if self.in_failure_case == 1:
    #                 self.in_failure_case = 0 
            
    #             if self.action_json.index(action) + 1 > len(self.action_json):
    #                 return 0
    #             else:
    #                 action = self.action_json[self.action_json.index(action) + 1]

    #     # Return the next action
    #     logging.debug("Next action: " + str(action["id"]))
    #     return action
    
    # Resolves all of the params in an action
    def _resolve_params_in_item(self, item, component, log_output=False):
        # If the item is a string, check if it contains any parameters
        if isinstance(item, str):
            search_result = re.findall(r'\[[\w:]+\]', item)
            for param in search_result:
                # Get the param name and value
                param_section, param_name = self._parse_param_name(param, component)
                if log_output:
                    logging.debug(f"Parsed: Param: {param}, Section: {param_section}, Name: {param_name}")
                param_value = Params.get(param_section, param_name)
                if param_value == None:
                    # If param not found in current component, set section to None to see if it's in global or module
                    param_value = Params.get(None, param_name)
                if param_value == None:
                    return item
                if log_output:
                    logging.debug(f"Found Parameter in Action. Replacing [{param_name}] with {param_value}")
                # Replace the param in the action with the value from the params
                item = item.replace(param, str(param_value))
            return item
            
        # If the item is a list or dict, recursively check each item in them
        else:
            if isinstance(item, list):
                for i in range(len(item)):
                    item[i] = self._resolve_params_in_item(item[i], component)
            elif isinstance(item, dict):
                for key in item:
                    if key in ["id", "type", "name", "left_term", "right_term", "children"]:
                        continue
                    item[key] = self._resolve_params_in_item(item[key], component)
            else:
                # TODO: Handle other types?
                pass

        return item

    def _parse_param_name(self, name, component):
        name = name.strip("[]")
        section = component
        # section = 'global'
        l = name.split(':')
        if len(l) == 1:
            name = l[0]
        elif len(l) == 2:
            section = l[0]
            name = l[1]
        else:
            logging.error(f"Invalid parameter name: {name}")
            self.fail(f"Invalid parameter name: {name}")
        return section, name
    
    # Run the actions and process the results
    # Returns 0 if all actions succeeded, 1 if any action failed, -1 if a loop is being exited
    def run_actions(self, action_json=None, fail_on_error=True, wrap_try=False, log_output=False):
        # If no action_json is provided, use the class action_json
        if action_json is None:
            action_json = self.action_json

        # keep track of the last if statement result
        last_if_result = None

        # keep track of the last try statement result
        last_try_result = None

        # Loop through the actions and process them
        for action in action_json:
            # replace any parameters in the action with the values from the params
            component = None
            if "component" in action:
                component = action["component"]
            if log_output:
                logging.debug(f"Resolving params in action: {component}:{action}")
            action = self._resolve_params_in_item(action, component)


            if action["type"] == "Next Loop":
                # In loop, return now to skip to the next loop
                return 0
            
            elif action["type"] == "Exit Loop":
                # In loop, return with the -1 exit code to break out of the loop without returning an exception result
                return -1
            
            elif action["type"] == "Loop":
                # Loop through the actions the specified number of times
                for i in range(int(float(action["count"]))):
                    action_result = self.run_actions(action["children"], fail_on_error=False)
                    # Some action failed, or a break was called, exit out of the loop
                    if action_result != 0:
                        break

                # action_result was breaking out of the loop, return success
                if action_result == -1:
                    action_result = 0
            
            elif action["type"] == "Try":
                # Try block, run the actions in the try block
                # Don't set the action result yet, we need to check the except and else blocks first and that happens on the next loop.
                last_try_result = self.run_actions(action["children"], fail_on_error=False)
                continue
                

            elif action["type"] == "Except":
                # Except block, run the actions in the except block
                if last_try_result == 1:
                    action_result = self.run_actions(action["children"], fail_on_error=False)
                else:
                    continue
            
            elif action["type"] == "On Success":
                # Else block, run the actions in the else block
                if last_try_result == 0:
                    action_result = self.run_actions(action["children"], fail_on_error=False)
                else:
                    continue

            elif action["type"] == "End Try":
                last_try_result = None
                

            elif action["type"] == "If":
                if self._evaluate_statement(action, component):
                    logging.info(f"Evaluating: IF {action['left_term']} {action['eval_method']} {action['right_term']} to True")
                    last_if_result = True
                    action_result = self.run_actions(action["children"], fail_on_error=False)
                else:
                    logging.info(f"Evaluating: IF {action['left_term']} {action['eval_method']} {action['right_term']} to False")
                    last_if_result = False
                    continue

            elif action["type"] == "Else If":
                if last_if_result is False:
                    if self._evaluate_statement(action, component):
                        last_if_result = True
                        action_result = self.run_actions(action["children"], fail_on_error=False)
                    else:
                        last_if_result = False
                        continue
                else:
                    continue

            elif action["type"] == "Else":
                if last_if_result is False:
                    action_result = self.run_actions(action["children"], fail_on_error=False)
                else:
                    continue

            elif action["type"] == "End If":
                last_if_result = None
                continue

            else:
                # Run the action
                if wrap_try:
                    # This is to prevent failure in kill() routines.
                    try:
                        action_result = self.process_action(action)
                    except:
                        print(" WARNING - action failed.")
                        pass
                else:
                    action_result = self.process_action(action)
            
            # If the action failed, stop processing and return 1 to indicate failure
            if action_result == 1:
                if fail_on_error:
                    logging.error(f"Action failed: {action['id']}")
                    self.fail("Failure to run action: " + str(action["id"]))
                return 1

            # If the action was exit loop and was nested in another action such as If statement, return -1 to exit the loop
            if action_result == -1:
                return -1
        
        # Return 0 if all actions succeeded
        return 0

    def _evaluate_statement(self, action, component=None, log_output=False):
        lt = action["left_term"]
        if log_output:
            logging.debug(f"Evaluating statement: {component} {lt}")
        left_term = self._resolve_params_in_item(action["left_term"], component)
        # if left_term is a string, try to convert it to an int or float
        if isinstance(left_term, str):
            try:
                left_term = float(left_term)
            except ValueError:
                pass
        if log_output:
            logging.debug(f"Evaluated left term: {left_term}")
        right_term = self._resolve_params_in_item(action["right_term"], component)
        if isinstance(right_term, str):
            try:
                right_term = float(right_term)
            except ValueError:
                pass
        eval_method = action["eval_method"]
        if log_output:
            logging.debug(f"Evaluated right term: {right_term}")
        # Evaluate the if statement for each type of comparison
        if eval_method == "==":
            return left_term == right_term
        elif eval_method == "!=":
            return left_term != right_term
        elif eval_method == ">":
            return left_term > right_term
        elif eval_method == "<":
            return left_term < right_term
        elif eval_method == ">=":
            return left_term >= right_term
        elif eval_method == "<=":
            return left_term <= right_term
        elif eval_method == "in":
            return str(left_term) in str(right_term)
        elif eval_method == "not in":
            return str(left_term) not in str(right_term)

    # callback for before the action is processed
    def before_action(self, action):
        pass

    # callback for after the action is processed
    def after_action(self, action):
        pass

    # Returns the action with the matching id or None if the action is not found
    # TODO: there can be more than one.  Search backwards for most recent?
    def get_action_by_id(self, id, json=None):
        # If no json is passed in, use the input json
        if json is None:
            json = self.action_json

        ret_action = None
        # Loop through the json to find the action with the matching id
        for action in json:
            if action["id"] == id:
                return action
            if "children" in action and action["children"] != []:
                ret_action = self.get_action_by_id(id, action["children"])
                if ret_action != None:
                    return ret_action
        
        # If the action is not found, return None
        return None

    # Return a list of actions with the matching description or None if the action is not found
    def get_action_by_description(self, description, json=None):
        if json is None:
            json = self.action_json
        matching_actions = []
        for action in json:
            if action["description"] == description:
                matching_actions.append(action)
        if len(matching_actions) == 0:
            return None
        elif len(matching_actions) == 1:
            return matching_actions[0]
        return matching_actions
                
    # Return a list of actions with the matching description substring or None if the action is not found
    def get_action_by_description_substring(self, description, json=None):
        if json is None:
            json = self.action_json
        matching_actions = []
        for action in json:
            if description in action["description"]:
                matching_actions.append(action)
        if len(matching_actions) == 0:
            return None
        elif len(matching_actions) == 1:
            return matching_actions[0]
        return matching_actions

    # Find the next action of a particular type
    # If json is not passed in, use the action_json
    # Returns the next action of the type or None if the action is not found
    def _find_next_type(self, type, json=None):
        if json is None:
            json = self.action_json

        nesting_count=0
        # Loop through the json to find the next action of the type
        # count the nesting of try blocks and only return the action if the nesting is 0 (same level)
        for action in json:
            if action["type"] == "Try":
                nesting_count += 1
            if action["type"] == type:
                if nesting_count == 0:
                    return action
                else:
                    nesting_count -= 1

        # If the action is not found, return None
        return None
    
    def _set_params(self, param_name, param_value, component, log_output=False):
        # turn the param_name and param_value into lists if they are not already
        if not isinstance(param_name, list):
            param_name = [param_name]

        if not isinstance(param_value, list):
            param_value = [param_value]

        # If the param_name and param_value are not the same length, raise an exception
        if len(param_name) != len(param_value):
            raise Exception("Parameter name and value lists are not the same length")
        
        # Loop through the param_name and param_value lists and set the params
        for i in range(len(param_name)):
            param_section, param_name = self._parse_param_name(param_name[i], component)
            if param_section == None:
                param_section = Params.get('global', 'module_name')
            param_value = param_value[i]
            # Set the parameter in the params dictionary
            Params.setParam(param_section, param_name, param_value)
            if log_output:
                logging.debug(f"Set parameter: {param_section}:{param_name} = {param_value}")

    def _delete_params(self, param_name, component, log_output=False):
        # turn the param_name into a list if it is not already
        if not isinstance(param_name, list):
            param_name = [param_name]

        # Loop through the param_name and delete the params
        for i in range(len(param_name)):
            param_section, param_name = self._parse_param_name(param_name[i], component)
            if param_section == None:
                param_section = Params.get('global', 'module_name')
            # Delete the parameter in the params dictionary
            Params.deleteParam(param_section, param_name)
            if log_output:
                logging.debug(f"Deleted parameter: {param_section}:{param_name}")

    # Flatten the json to make it easier to process
    # Directory offset is used to adjust the image paths for include sequences, leave as None for the top level json
    def _flatten_json(self, json_object, directory_offset=None, component=None, log_output=False):
        if log_output:
            logging.debug("Flattening JSON, directory_offset: " + str(directory_offset) + ", component: " + str(component))
        flat_json = []
        for action in json_object:
            # Skip disabled actions
            if "enabled" in action and action["enabled"] == False:
                continue

            # For setting the scope of parameters
            action["component"] = component

            if directory_offset == None:
                directory_offset = self.json_parent_dir
                if log_output:
                    logging.debug("Using json_parent_dir as directory_offset: " + str(directory_offset))
            # logging.debug("Directory offset: " + directory_offset)

            # If the action is an include, read the json from the file and flatten it into the current json object
            if action["type"] == "Include":

                relative_path = action["include_path"]
                base_folder = os.path.basename(relative_path)

                full_path = os.path.join(directory_offset, relative_path)
                if not os.path.exists(full_path):
                    full_path = self.resolve(relative_path)
                full_path = os.path.join(full_path, base_folder + ".json")

                # Create a new action for the include and add it to the action_json
                if "params" in action:
                    new_action = {}
                    new_action["type"] = "Set Params"
                    new_action["description"] = f"Setting parameters: {action['params']}"
                    new_action["id"] = "AUTO"
                    new_action["params"] = action["params"]
                    new_action["component"] = base_folder
                    new_action["caller"] = component
                    flat_json.append(new_action)

                # Flatten include
                # logging.debug("Including: " + base_folder)
                # logging.debug("Including: " + full_path)
                with open(full_path, 'r') as file:
                    data = json.load(file)
                flat_json = flat_json + self._flatten_json(data, os.path.dirname(full_path), component=base_folder)

                # Add in delete params action here
                if "params" in action:
                    new_action = {}
                    new_action["type"] = "Delete Params"
                    new_action["description"] = "Delete params from after include"
                    new_action["id"] = "AUTO"
                    new_action["params"] = action["params"]
                    new_action["component"] = base_folder
                    flat_json.append(new_action)

                # Don't add the include action to the flat json
                continue

            # Add the action to the flat json
            flat_json.append(action)

            # # If the action has children, flatten them in the same way
            if "children" in action:
                # logging.debug("Flattening children of: " + str(action["id"]))
                action["children"] = self._flatten_json(action["children"], directory_offset, component=component)
            
            # If the templates are located in a different directory, adjust the path of the image
            # This is used for include to adjust the image paths to the correct directory
            if directory_offset is not None and 'file_name' in action:
                new_file_name = []
                for image in action["file_name"]:
                    if log_output:
                        logging.debug("Adjusting image path: " + str(image) + " to " + os.path.join(directory_offset, image))
                    new_file_name.append(os.path.join(directory_offset, image))
                action["file_name"] = new_file_name
        
        # # Debug prints to see the flattened json
        # for action in flat_json:
        #     logging.debug("Flattened action: " + str(action["id"]))

        return flat_json

    # Load the json into the action_json to prepare it for processing. Allows for using get_next_action to get the first action
    def load_action_json(self, json_file):
        self._cleanup_captures()
        self.json_parent_dir = os.path.dirname(json_file)
        with open(json_file, 'r') as file:
            data = json.load(file)
        self.action_json = self._flatten_json(data, directory_offset=None, component=os.path.basename(self.json_parent_dir)) # Flatten the json to grab any includes. Load the JSON into action_json
        return self.action_json

    # Cleanup the captures dictionary
    def _cleanup_captures(self):
        self.captures = {}

    # Process a particular action
    def process_action(self, action, log_output=False):
        # Skip disabled actions
        if "enabled" in action and action["enabled"] == False:
            return 0
                
        component = None
        if "component" in action:
            component = action["component"]
        
        caller = None
        if "caller" in action:
            caller = action["caller"]

        if log_output:
            logging.debug(f"Processing action: {component}:{action}")

        if action["type"] in ["Information", "Comment", "Setup", "Run Test", "Teardown", "Set Default", "Set User Default", "Loop", "End Loop", "If", "Else If", "Else", "End If", "Try", "Except", "End Try", "On Success"]:
            return 0
        
        self.component = component
        # logging.info(f"Setting self.component to {self.component}")

        if action['id'] != "AUTO":
            if action['type'] in ["Set", "Set Default", "Increment", "Decrement"]:
                logging.info(f"[{self.daq_accumulated_time}] Action {action['id']}: {action['type']} {action['name']}, {action['value']}")
            elif action['type'] in ["Set Display", "Window Move"]:
                logging.info(f"[{self.daq_accumulated_time}] Action {action['id']}: {action['type']}, {action['screen']}")
            else:
                logging.info(f"[{self.daq_accumulated_time}] Action {action['id']}: {action['type']} {action['description']}")

            # Append the action to the csv of actions
            if self.log_scenario_events:
                scenario_events_file        = os.path.join(self.result_dir, "scenario_events.csv")
                scenario_events_file_exists = os.path.exists(scenario_events_file)
                with open(scenario_events_file, 'a', newline='') as file:
                    writer = csv.writer(file)
                    if not scenario_events_file_exists:
                        writer.writerow(["Time", "Event"])
                    writer.writerow([self.daq_accumulated_time, f'{action["type"]}: {action["description"]}'])

        # Load the capture if it is not already in memory
        # TODO: This seems like it's loading the thumbnail from the authoring tool instead of throwing an error, which seems dangerous.
        if "capture_id" in action:
            if action["capture_id"] not in self.captures:
                logging.debug("Capture not in memory. Loading capture: " + str(action["capture_id"]))
                action["capture_id"] = cv.imread(os.path.join(self.json_parent_dir, "image_" + str(action["capture_id"]) + ".png" ), cv.IMREAD_GRAYSCALE)
                self.fail("Shouldn't reach here") 

        if "match_threshold" in action and action["match_threshold"] != "":
            threshold = float(action["match_threshold"])
        else:
            threshold = None

        except_flag = False         # Initialize the exception flag to false
        
        ### Handle traceId for typing actions. ###
        if not "traceId" in action: 
            action["traceId"] = ""
            action["traceX"]= 0
            action["traceY"]= 0
            action["traceW"]= 0
            action["traceH"]= 0
            action["traceMs"] = 0
            action["traceFramerate"]= 0
            logging.debug("No traceId found in action, setting to empty string and trace dimensions to 0")

        # create traceId dictionary if it doesn't exist
        if not hasattr(self, 'traceId_dict'):
            self.traceId_dict = {}
        if action["traceId"] != "":
            if action["traceId"] in self.traceId_dict:
                self.traceId_dict[action["traceId"]] += 1
            else:
                self.traceId_dict[action["traceId"]] = 1
            action["traceId"] = f"{action['traceId']}_{self.traceId_dict[action['traceId']]}"    
        ###########################################

        # Find the template in the screenshot and click on it on the DUT
        if action["type"] == "Click":
            filename = action["file_name"]
            primary = True
            if "primary" in action:
                logging.debug(f"Clicking by template: primary: {action['primary']}")
                primary = action["primary"] == True
            logging.debug(f"Clicking by template: {filename[0]}, primary: {primary}")
            # primary = action["primary"] == True if "primary" in action else True
            edge_thresholds = []
            if "edge_thresholds" in action:
                threshold_str = action["edge_thresholds"]
                edge_thresholds = [int(x) for x in threshold_str.split(',')]
            scale = self.default_scale
            if "scale" in action and action["scale"] != "":
                # If the scale is specified in the action, use it
                # The scale is a string of comma-separated values, e.g. "0.8,1.0"
                # Convert it to a list of floats
                scale_str = action["scale"]
                scale = [float(x) for x in scale_str.split(',')]
            if self._click_by_template(action["file_name"], action["id"], action["capture_id"], threshold=threshold, delay=self.default_click_time, x=float(action["x"]), y=float(action["y"]), scale=scale, primary=primary, edge_detect_thresholds=edge_thresholds, traceId=action["traceId"], traceX=action["traceX"], traceY=action["traceY"], traceW=action["traceW"], traceH=action["traceH"], traceMs=action["traceMs"], traceFramerate=action["traceFramerate"]):
                logging.debug("Click successful")
            else:
                except_flag = True

        elif action["type"] == "Click Coord":
            x_frac = action['x']
            y_frac = action['y']
            logging.debug(f"Clicking by coordinates: {x_frac}, {y_frac}")
            # primary = action["primary"] == "1" if "primary" in action and action["primary"] == "1" else True
            primary = True
            screen_width, screen_height = self._get_screen_size(self.current_screen)
            x = int(float(x_frac) * screen_width * self.dut_coord_scaler)
            y = int(float(y_frac) * screen_height * self.dut_coord_scaler)
            # Click the point
            rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Tap", int(x), int(y), 100, primary, self.current_screen, action["traceId"], action["traceX"], action["traceY"], action["traceW"], action["traceH"], action["traceMs"], action["traceFramerate"])

        # Find the template in the screenshot and move the mouse to it on the DUT
        elif action["type"] == "Move":
            logging.debug("Moving by template: " + str(action["file_name"][0]))
            scale = self.default_scale
            if "scale" in action and action["scale"] != "":
                # If the scale is specified in the action, use it
                # The scale is a string of comma-separated values, e.g. "0.8,1.0"
                # Convert it to a list of floats
                scale_str = action["scale"]
                scale = [float(x) for x in scale_str.split(',')]
            if self._move_by_template(action["file_name"], action["capture_id"], threshold=threshold, delay=self.default_click_time, x=float(action["x"]), y=float(action["y"]), scale=scale):
                logging.debug("Move successful")
            else:
                except_flag = True

        # Send typing to the DUT
        elif action["type"] == "Type":
            logging.debug(f"Typing: {action['description']}")
            typing_delay = int(action["typing_delay"]) if "typing_delay" in action else self.typing_delay
            self._send_text(action["text"], typing_delay=typing_delay, traceId=action["traceId"], traceX=action["traceX"], traceY=action["traceY"], traceW=action["traceW"], traceH=action["traceH"], traceMs=action["traceMs"], traceFramerate=action["traceFramerate"])
            if "delay" in action:
                calculated_delay_time = (typing_delay / 1000.0) * len(action["text"])
                if float(action["delay"]) < calculated_delay_time:
                    logging.debug(f"Typing delay {action['delay']} is less than calculated delay {calculated_delay_time}. Using calculated delay.")
                    action["delay"] = str(calculated_delay_time)

        # Inject a scroll event
        elif action["type"] == "Scroll":
            logging.debug("Scrolling: " + str(action["direction"]))
            self._scroll(x_frac=float(action["x"]), y_frac=float(action["y"]), direction=action["direction"], traceId=action["traceId"], traceX=action["traceX"], traceY=action["traceY"], traceW=action["traceW"], traceH=action["traceH"], traceMs=action["traceMs"], traceFramerate=action["traceFramerate"])

        # Check for a template match in a screenshot. Returns True if the template is found, False if it is not
        elif action["type"] == "Check":
            logging.debug("Checking by template: " + str(action["file_name"][0]))
            scale = self.default_scale
            if "scale" in action and action["scale"] != "":
                # If the scale is specified in the action, use it
                # The scale is a string of comma-separated values, e.g. "0.8,1.0"
                # Convert it to a list of floats
                scale_str = action["scale"]
                scale = [float(x) for x in scale_str.split(',')]
            if self._check_by_template(action["file_name"], action["capture_id"], threshold=threshold, scale=scale):
                logging.debug("Check matched")
            else:
                logging.warning("Check did not match")
                except_flag = True

        # Run a command on the DUT and check the exit code
        elif action["type"] == "Command":
            result = self._call(["cmd.exe", "/c " + action["command"]])
            logging.debug("Command result: " + str(result))
            if "expected_exit_code" in action:
                if action["expected_exit_code"] != "" or result != action["expected_exit_code"]:
                    except_flag = True

        # Insert a specified block of code 
        elif action["type"] == "Code":
            path = action["file_name"][0]
            module_name = os.path.basename(path).replace(".py", "")
            logging.debug(f"Executing code block module: {module_name} at: {path}")
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            module.run(self)

        # Sleep for the specified amount of time
        elif action["type"] in ["Delay", "Delay To"]:
            # Delay will happen below
            pass

        # Capture the screen for the given region. Skip if the capture is already in memory unless recapture is specified
        elif action["type"] == "Capture":
            if action["id"] not in self.captures:
                # logging.debug("Capturing screen: " + str(action["id"]))
                self.captures[action["id"]]=self._capture_screen(action["file_name"][0], x=float(action["x"]), y=float(action["y"]), w=float(action["w"]), h=float(action["h"]))
            
            elif "recapture" in action and action['recapture'] == True:
                # logging.debug("Re-capturing screen: " + str(action["id"]))
                self.captures[action["id"]]=self._capture_screen(action["file_name"][0], x=float(action["x"]), y=float(action["y"]), w=float(action["w"]), h=float(action["h"]))

            else:
                logging.debug("Capture already in memory: " + str(action["id"]))
        
        # Continue to check for a template match in a screenshot until found/ not found or until the timeout is reached
        elif action["type"] == "Check Until Found" or action["type"] == "Check Until Not Found":
            logging.debug("Checking by template until found/not found: " + str(action["file_name"][0]))
            # Grab the start time for the timeout
            start_time = datetime.now()
            edge_thresholds = []
            if "edge_thresholds" in action:
                threshold_str = action["edge_thresholds"]
                edge_thresholds = [int(x) for x in threshold_str.split(',')]

            # Loop until the timeout is reached or the template is found/ not found
            while (datetime.now() - start_time).total_seconds() < float(action["timeout"]):
                self.captures[action["capture_id"]]=self._capture_screen("check.png", x=float(action["x"]), y=float(action["y"]), w=float(action["w"]), h=float(action["h"]))
                # Template found
                if self._check_by_template(action["file_name"], action["capture_id"], threshold=threshold, edge_detect_thresholds=edge_thresholds):
                    # If we are checking until found, return success
                    if action["type"] == "Check Until Found":
                        logging.info("Match present, returning success")
                        break
                    # If we are checking until not found, sleep and check again
                    else:
                        logging.info("Match still present, sleeping")
                        self._sleep_by(float(action["delay"]))
                # Template not found
                else:
                    # If we are checking until not found, return success
                    if action["type"] == "Check Until Not Found":
                        logging.info("Match not present, returning success")
                        break
                    # If we are checking until found, sleep and check again
                    else:
                        logging.info("Match not present, sleeping")
                        self._sleep_by(float(action["delay"]))
            # Check if the timeout was reached
            if (datetime.now() - start_time).total_seconds() >= float(action["timeout"]):
                logging.warning("Timeout reached, returning failure")
                except_flag = True
        
        # Decrement a parameter
        elif action["type"] == "Decrement":
            param = str(action['name']).strip("[]")
            dec_value = float(self._resolve_params_in_item(action['value'], component))
            param_section, param_name = self._parse_param_name(param, component)
            param_value = float(Params.get(param_section, param_name))
            new_value = str(param_value - dec_value)
            logging.debug(f"Decrementing parameter {param_section}:{param_name} to {new_value}")
            Params.setParam(param_section, param_name, new_value)

        # Increment a parameter
        elif action["type"] == "Increment":
            param = str(action['name']).strip("[]")
            inc_value = float(self._resolve_params_in_item(action['value'], component))
            param_section, param_name = self._parse_param_name(param, component)
            param_value = float(Params.get(param_section, param_name))
            new_value = str(param_value + inc_value)
            logging.debug(f"Incrementing parameter {param_section}:{param_name} to {new_value}")
            Params.setParam(param_section, param_name, new_value)

        # Set the parameters in the params dictionary
        elif action["type"] == "Set Params" or action["type"] == "Set":
            if "params" in action:
                for param in action["params"]:
                    # logging.info(f"Set Params: {action}")
                    # param_name = action["scope"] + "_" + param["name"]
                    param_name = param["name"]
                    # For the case of values in an include block, set caller as the section
                    param_val = self._resolve_params_in_item(param['value'], caller)

                    # logging.info(f'Set param - {param_name} = {param_val}')
                    self._set_params(param_name, param_val, component)
            else:
                # logging.info(f'Set action - {action["name"]} = {action["value"]}')
                self._set_params(action["name"], action["value"], component)

        elif action["type"] == "Set Display":
            self.current_screen = int(action["screen"])

        elif action["type"] == "Window Move":
            typing_delay = int(action["typing_delay"]) if "typing_delay" in action else self.typing_delay
            self._send_window_move(typing_delay, int(action["screen"]))

        elif action["type"] == "Window Maximize":
            self._send_window_maximize()

        # Delete the parameters from the params dictionary
        elif action["type"] == "Delete Params":
            for param in action["params"]:
                # param_name = action["scope"] + "_" + param["name"]
                param_name = param["name"]
                self._delete_params(param_name, component)

        # Fail the scenario
        elif action["type"] == "Fail":
            msg = "Fail action: " + str(action['description'])
            logging.error(msg)
            self.fail(msg)

        # Stop processing the current list of actions
        elif action["type"] == "End":
            return 1

        else:
            raise Exception("Unknown action type: " + action["type"])

        # Manage the exception flags as directed if specified in the action
        if "exception_on" in action:

            # A match should be a fail
            if action["exception_on"] == "Match":
                # If we matched, then set everything to failure
                if not except_flag:
                    except_flag = True
                # If we didn't match, then set everything to success
                else:
                    except_flag = False

            # A no match should be a fail
            elif action["exception_on"] == "No match":
                # If we didn't match, then set everything to failure
                if except_flag:
                    except_flag = True
                # If we matched, then set everything to success
                else:
                    except_flag = False
            
            # We shoulf never fail, regardless of the match result
            else:
                except_flag = False
        
        # Save the screen if the action failed
        if except_flag:
            logging.warning("Action failed: " + str(action["id"]))
            if "capture_id" in action:
                self._save_screen("exception_" + str(action["id"] + ".png"), self.captures[action["capture_id"]])
            
            return 1 # Return failure

        # Handle Delay
        if action['type'] == "Delay To":
            self._sleep_to(float(action["delay"]))
        elif "delay" in action:
            self._sleep_by(float(action["delay"]))
        return 0 # Return success

        # ###########################################################################################
        # End of processing of the action ###########################################################
        # ###########################################################################################
        # TODO: May be able to optimize this section a lot more
        # We need to check if we are in an except block and set the flag accordingly. This is to support being able to arbitrarily pass a particular action,
        # potentially one that is in an except block, and still be able to process the next action correctly
        # if self._find_next_type("else", self.action_json[self.action_json.index(action):]) is not None:
        #     # There is an else block after this action
        #     index_of_next_else = self.action_json.index(self._find_next_type("else", self.action_json[self.action_json.index(action):]))
            
        #     if self._find_next_type("except", self.action_json[self.action_json.index(action):]) is not None:
                
        #         # There is an except block after this action
        #         index_of_next_except = self.action_json.index(self._find_next_type("except", self.action_json[self.action_json.index(action):]))
                
        #         # If the else block is before the except block, we must already be in an except block
        #         if index_of_next_else < index_of_next_except:
        #             self.in_failure_case = 1
        #     else:
        #         # There is no more except blocks but there is an else block, therefore we are in an except block already
        #         self.in_failure_case = 1

# ############################################################################################################
# ############################################################################################################
# ############################################################################################################





    def _mark_trace(self, tag):
        if self.trace == "1":
            if Params.get('global', 'trace_filemode') == '1':
                self._call(["cmd.exe", '/c wpr.exe -marker ' + tag + ' -instancename perfTrace'])
            else:
                self._call(["cmd.exe", '/c wpr.exe -marker ' + tag])

    def _assert(self, assert_list):
        logging.error(assert_list)
        raise AssertionError("\n\nThe following requirements to run " + self._module + " have not been met:\n\n" + assert_list)

    def error_fail(self, msg):
        logging.error(msg)
        self.fail(msg)

    def _wait_for_dut_comm(self):
        if Params.get("global", "local_execution") == "1":
            return
        
        sleep_wake_call = Params.get('global', 'sleep_wake_call')
        hard_reboot_call = Params.get('global', 'hard_reboot_call')
            
        count = 0
        count_timeout = 20

        # Poll for simple remote to determine if DUT is alive
        while(True):
            logging.info("Waiting for DUT communication")
            #logging.info("the count is currently " + str(count))
            try:
                rpc.call_rpc(self.dut_ip, self.rpc_port, "GetVersion", [], log=False)
                logging.info("DUT is alive")
                break
            except:
                if self.timeout_wake == '1':
                    if count/count_timeout == 1 or count/count_timeout == 2:
                        logging.info("Toggling DUT power")
                        self._host_call(sleep_wake_call)
                    elif count/count_timeout == 3:
                        logging.info("Going Hard Reboot")
                        self._host_call(hard_reboot_call)
                time.sleep(10)
                count += 1
                continue

    def _check_local_exec_reboot(self):
        if self.dut_ip == "127.0.0.1" and self.platform.lower() == "windows":
            Params.setCalculated("local_execution_reboot", "1")
            dashboard_url = Params.get('global', 'dashboard_url')

            if dashboard_url != "":
                dashboard_plan_id = Params.get('global', 'dashboard_plan_id')

                url = urlunparse(
                    urlparse(dashboard_url)._replace(
                        path='/plan/PausePlan',
                        query=f"PlanIDs={dashboard_plan_id}"
                    )
                )

                requests.get(url, allow_redirects=False)
                # Build the post-reboot command to run the wait_and_resume_plan.ps1 script
                base_url = urlunparse(urlparse(dashboard_url)._replace(path='',query='', fragment=''))

                # post_reboot_script = r"C:\hobl_bin\wait_and_resume_plan.ps1"
                hobl_path = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
                post_reboot_script = os.path.join(hobl_path, "utilities", "open_source", "wait_and_resume_plan.ps1")
                post_reboot_call = f'powershell.exe -ExecutionPolicy Bypass -File "{post_reboot_script}" -PlanID {dashboard_plan_id} -ServerUrl "{base_url}"'
                
                reg_cmd = f'reg.exe add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v LocalExec_PostReboot /t REG_SZ /d "{post_reboot_call}" /f'
                self._call(["cmd.exe", "/c " + reg_cmd])
                logging.info(f"Set RunOnce registry to resume plan {dashboard_plan_id} after reboot")
            return True
        return False

    def _dut_reboot(self, to_uefi=False):
        if self._check_local_exec_reboot():
            return

        if self.platform.lower() == "windows":
            if to_uefi:
                logging.info("Rebooting DUT to UEFI")
                self._call(["shutdown.exe", "/r /f /t 5 /fw"])
            else:
                logging.info("Rebooting DUT")
                self._call(["shutdown.exe", "/r /f /t 5"])
        elif self.platform.lower() == "macos":
            logging.info("Rebooting DUT")
            self._call(["zsh", f'-c "echo {self.dut_password} | sudo -S shutdown -r now"'])
        else:
            logging.error("Unsupported platform")
        time.sleep(15)
        self._wait_for_dut_comm()

    def _get_start_button(self, driver):
        start_button = None
        try:
            # New UI
            start_button = driver.find_element_by_class_name("Windows.UI.Input.InputSite.WindowClass").find_element_by_name("Start")
        except:
            # Old UI
            start_button = driver.find_element_by_name("Start")
        return start_button

    def _get_search_button(self, driver):
        # Search button isn't working well, so just get Start button instead
        return self._get_start_button(driver)

        # OBSOLETE...
        search_button = None
        try:
            # New UI
            # Click Start button first, otherwise coordinates of Search button don't work right (bug in UI).  It will grab the top-left corner
            # instead of the center.
            start_button = driver.find_element_by_class_name("Windows.UI.Input.InputSite.WindowClass").find_element_by_name("Start")
            start_button.click()
            search_button = driver.find_element_by_class_name("Windows.UI.Input.InputSite.WindowClass").find_element_by_name("Search")
        except:
            # Old UI
            search_button = driver.find_element_by_name("Start")
        return search_button

    def _get_app_tray(self, driver):
        apps_elem = None
        try:
            apps_elem = driver.find_element_by_class_name("Shell_TrayWnd").find_element_by_class_name("Windows.UI.Input.InputSite.WindowClass")
        except:
            apps_elem = driver.find_element_by_class_name("Shell_TrayWnd").find_element_by_name("Running applications")
        return apps_elem

    def _add_input_call(self, json_name, image_name, start_time):
        if image_name == None or image_name == "":
            return
        self.inputInject_startTime[image_name] = [json_name, start_time]

    def _sleep_to(self, t):
        self.scenario_prev_time = self.daq_prev_time = time.time()
        delta = t - (self.scenario_prev_time - self.scenario_start_time)
        
        self.scenario_accumulated_time = t
        self.daq_accumulated_time = t

        logging.info(f"Sleeping for {delta:.2f} to {t:.2f}")
        if delta < 0:
            delta = 0
        time.sleep(delta)

    def _sleep_by(self, t):
        self._sleep_to(self.scenario_accumulated_time + t)

    def _sleep_to_now(self):
        # Advance t to the current time
        t = self.scenario_accumulated_time + (time.time() - self.scenario_prev_time)
        # round up t to the nearest second
        t = math.ceil(t)
        self._sleep_to(t)

    def _write_events_file(self, json_name, start_time):
        if self.daq_start_time == 0:
            return
        jsonFile = open(os.path.join(self.training_path_host, json_name))
        readJson = json.load(jsonFile)

        eventsFilePath = self.result_dir + os.sep + 'scenario_events.csv'
        start_time = start_time - self.daq_start_time
        if not os.path.exists(eventsFilePath):
            with open (eventsFilePath,'a', newline='') as eventsFile:
                csv_writter = csv.writer(eventsFile)
                title = ['Event', 'Time']
                csv_writter.writerow(title)

        with open (eventsFilePath,'a', newline='') as eventsFile:
            csv_writter = csv.writer(eventsFile)
            for index in readJson:
                try:
                    tag = index["tag"]
                    cmd = index["cmd"]
                    # if cmd == "sleep":
                    #     continue
                    accum_delay = index["accum_delay"]
                    delay = float(accum_delay)/1000
                except:
                    continue
                timestamp = delay + start_time
                json_name_base = json_name.replace(".json", "")
                csv_writter.writerow([json_name_base + ": " + tag, "{:.3f}".format(timestamp)])

                # if (index["cmd"] == "screenshot"):
                #     return (float(index["accum_delay"])/1000.0) + start_time - self.scenario.video_startTime

    def _write_events_file_custom(self, tag, start_time):
        if self.daq_start_time == 0:
            return

        eventsFilePath = self.result_dir + os.sep + 'scenario_events.csv'
        if not os.path.exists(eventsFilePath):
            with open (eventsFilePath,'a', newline='') as eventsFile:
                csv_writter = csv.writer(eventsFile)
                title = ['Event', 'Time']
                csv_writter.writerow(title)

        t_offset = start_time - self.daq_start_time
        with open (eventsFilePath,'a', newline='') as eventsFile:
            csv_writter = csv.writer(eventsFile)
            csv_writter.writerow([tag, "{:.3f}".format(t_offset)])


    # Deprecated function, kept for reference
    # def _call_input_inject(self, training_path, json_name, image_name, start_time, perf_mode=""):
    #     json_path = os.path.join(training_path, json_name)
    #     self._add_input_call(json_name, image_name, start_time)
    #     # Write to events file
    #     self._write_events_file(json_name, start_time)
    #     self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), json_path + " " + perf_mode])
    
    def check_battery_level(self):
        result_battery_path = os.path.join(self.result_dir, "battery_level.txt")
        batteryfile = open(result_battery_path, 'r')
        lines = batteryfile.readlines()
        test_pass = False
        for line in lines:
            if "total battery" in line:
                battery = int(line.split("total battery: ")[-1])
                if (battery <= int(self.crit_batt_level) + 1):
                    test_pass = True
        if (test_pass):
            logging.info("Device successfully entered hibernate and woke up.")
        else:
            logging.error("Test timed out before critical battery level reached.")
            raise Exception("Command timeout occurred before critical battery level reached.  Critical battery level: " + self.crit_batt_level)
    

    def config_full_dur(self):
        result_battery_path = os.path.join(self.result_dir, "battery_level.txt")
        batteryfile = open(result_battery_path, 'r')
        lines = batteryfile.readlines()
        lowest = 100
        last = None
        for line in lines:
            if "total battery" in line:
                battery = int(line.split("total battery: ")[-1])
                if (battery <= lowest):
                    lowest = battery
                    prev_last = last
                    last = datetime.strptime(line.split(": total")[0], "%m/%d/%Y %I:%M:%S %p")
                    # purpose of this if else block below is to handle the case of device entering hibnerate before 
                    # it can write to file so it writes after it wakes up.
                    if prev_last is None: 
                        prev_last = last
                    else:
                        difference = (last-prev_last).total_seconds()/60
                        if difference > 10 and battery < 5:
                            last = prev_last

        first = datetime.strptime(lines[0].split(": total")[0], "%m/%d/%Y %I:%M:%S %p")
        minutes = (last-first).total_seconds()/60
        config_path = os.path.join(self.result_dir, self.testname + "_configPostFull.csv")
        file = open(config_path, 'w')
        file.write("Full Run Duration (min)" + "," + str(minutes))
        batteryfile.close()
        file.close()


    def _web_replay_start(self, disable_delay=False):
        version = self.web_replay_version

        if self.web_replay_recording == '':
            self.web_replay_recording = self.module

        if os.path.isabs(self.web_replay_recording):
            archive_file = self.web_replay_recording
        else:
            archive_file = f'C:\\web_replay\\{version}\\recordings\\{self.web_replay_recording}'

        self._web_replay_download(archive_file)

        if self.web_replay_run == '0' and self.web_replay_action == "netlog":
            browser_nospace = self.browser.lower().replace(" ", "")
            web_replay_ps1_args = f"live {self.dut_exec_path}\\web_replay\\netlog.json {browser_nospace}"

            self._call([
                "powershell.exe", f"{self.dut_exec_path}\\web_replay\\set_args.ps1 {web_replay_ps1_args}"
            ])
            return

        if self.web_replay_run == '0':
            return

        logging.debug("Killing any open browsers")

        if self.platform.lower() == "windows":
            try:
                self._kill("MicrosoftEdge.exe")
            except:
                pass
            try:
                self._kill("msedge.exe")
            except:
                pass
            try:
                self._kill("chrome.exe")
            except:
                pass

        if self.web_replay_action not in ["record", "replay", "bulk_record", "bulk_replay"]:
            raise Exception(f"Invalid web_replay action parameter: {self.web_replay_action}")

        web_replay_exe = f"C:\\web_replay\\{version}\\bin\\web_replay.exe"

        self._web_replay_firewall_check(version)
        action = self.web_replay_action

        if self.web_replay_action in ["record", "replay"] and self.web_replay_rand_ports == "1" and self.web_replay_ip == self.host_ip:
            self.web_replay_http_port = self._web_replay_find_free_port()
            self.web_replay_https_port = self._web_replay_find_free_port()

            Params.setOverride('global', 'web_replay_http_port', self.web_replay_http_port)
            Params.setOverride('global', 'web_replay_https_port', self.web_replay_https_port)

        if action in ["bulk_record", "bulk_replay"]:
            self._web_replay_set_browser_args()
            return

        web_replay_cmd_args  = f"--host=0.0.0.0"
        web_replay_cmd_args += f" --http_port={self.web_replay_http_port}"

        if self.platform.lower() == "windows":
            web_replay_cmd_args += f" --https_port={self.web_replay_https_port}"
        elif self.platform.lower() == "macos":
            web_replay_cmd_args += f" --http_proxy_port={self.web_replay_https_port}"

        if self.web_replay_ip == self.host_ip:
            web_replay_cmd_args += f" --out_dir={os.path.join(self.result_dir, 'web_replay')}"

        if action == "record" and self.web_replay_http_proxy_port:
            web_replay_cmd_args += f" --proxy_server_url=http://localhost:{self.web_replay_http_proxy_port}"

        if action == "replay" and self.web_replay_http_proxy_port:
            web_replay_cmd_args += f" --http_proxy_port={self.web_replay_http_proxy_port}"

        if action == "replay" and self.web_replay_excludes_list:
            web_replay_cmd_args += f" --excludes_list=\"{self.web_replay_excludes_list}\""

        use_light_theme = "1"

        if self.platform.lower() == "windows":
            use_light_theme = self._call([
                "powershell.exe",
                "(Get-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize).AppsUseLightTheme"
            ])

        if action == "replay":
            theme = "light" if use_light_theme == "1" else "dark"

            web_replay_cmd_args += f" --theme={theme}"

        # Optional argument to disable request delay
        if disable_delay:
            web_replay_cmd_args += f" --disable_req_delay"

        web_replay_cmd = f'{web_replay_exe} {action} {web_replay_cmd_args} {archive_file} > NUL 2>&1'

        logging.info(f"Starting web_replay")

        if self.web_replay_ip == self.host_ip:
            logging.debug(f"Running: {web_replay_cmd}")
            self._host_call(web_replay_cmd, cwd = f'C:\\web_replay\\{version}', blocking = False)
        else:
            try:
                output = self._web_replay_remote_server_start(archive_file, theme)

                if "result" in output:
                    result = json.loads(output)["result"][1].strip()
                    self.web_replay_http_port, self.web_replay_https_port = result.split(',')
                    Params.setOverride('global', 'web_replay_http_port', self.web_replay_http_port)
                    Params.setOverride('global', 'web_replay_https_port', self.web_replay_https_port)
                else:
                    logging.error("Could not launch web_replay server on remote host")
            except:
                logging.error("Could not launch web_replay server on remote host")

        reg_write("web_replay_http_port", self.web_replay_http_port)

        self._web_replay_set_browser_args()

        # Wait until server is responding
        available = False
        for i in range(30):
            try:
                logging.info("Checking for web_replay server availability...")
                self._web_replay_change_archive("init")
                if use_light_theme != "1":
                    self._web_replay_change_archive("init-dark")
                available = True
                break
            except:
                time.sleep(2)
        if not available:
            logging.error("web_replay server could not be started.")
            self.fail("web_replay server could not be started.")
        else:
            logging.info("web_replay server up")


    def _web_replay_kill(self):
        version = self.web_replay_version

        browser_nospace = self.browser.lower().replace(" ", "")
        web_replay_ps1 = f"{self.dut_exec_path}\\web_replay\\remove_args.ps1 {browser_nospace}"

        remove_cmd = ["powershell.exe", web_replay_ps1]

        reg_val = reg_read("web_replay_http_port")
        if reg_val.isdigit() and reg_clean("web_replay_http_port"):
            self.web_replay_http_port = reg_val

        if self.web_replay_run == '0' and self.web_replay_action == "netlog":
            self._call(remove_cmd)

            try:
                netlog_filename = "netlog.json"

                logging.info("Parsing generated netlog file")

                rpc.download(
                    self.dut_ip,
                    self.rpc_port,
                    os.path.join(self.dut_exec_path, f"web_replay\\{netlog_filename}"),
                    self.result_dir
                )

                outfile = f"C:\\web_replay\\{version}\\recordings\\idle_timeouts.json"

                self._host_call(
                    f"python.exe parse_netlog.py {self.result_dir}\\{netlog_filename} {outfile}",
                    cwd = f'C:\\web_replay\\{version}'
                )
            except:
                logging.error("Failed to parse netlog file")

            return

        if self.web_replay_run == '0':
            return

        if self.platform.lower() == "w365":
            Params.setOverride('web_kill', 'web_replay_remove_args_cmd', f'powershell.exe {web_replay_ps1}')
        elif self.platform.lower() == "macos":
            result = self._call(["networksetup", f'-listallnetworkservices'])
            services = result.splitlines()
            for service in services:
                if "*" in service:
                    continue
                self._call(["networksetup", f'-setwebproxystate "{service}" off'])
                self._call(["networksetup", f'-setsecurewebproxystate "{service}" off'])
        else:
            self._call(remove_cmd)

        logging.info("Killing web_replay")

        if self.web_replay_action in ["bulk_record", "bulk_replay"]:
            return

        try:
            requests.get(
                f'http://{self.web_replay_ip}:{self.web_replay_http_port}/web-page-replay-command-exit'
            )
        except:
            pass

        time.sleep(2)


    def _web_replay_set_browser_args(self):
        browser_nospace = self.browser.lower().replace(" ", "")
        web_replay_ps1_args = f"web_replay {self.web_replay_ip} {self.web_replay_http_port} {self.web_replay_https_port} {browser_nospace}"

        if self.platform.lower() == "w365":
            Params.setOverride('web_setup', 'web_replay_set_args_cmd', f'powershell.exe {self.dut_exec_path}\\web_replay\\set_args.ps1 {web_replay_ps1_args}')
        elif self.platform.lower() == "macos":
            result = self._call(["networksetup", f'-listallnetworkservices'])
            services = result.splitlines()
            for service in services:
                if "*" in service:
                    continue
                self._call(["networksetup", f'-setwebproxy "{service}" {self.web_replay_ip} {self.web_replay_http_port}'])
                self._call(["networksetup", f'-setsecurewebproxy "{service}" {self.web_replay_ip} {self.web_replay_https_port}'])
        else:
            self._call([
                "powershell.exe", f"{self.dut_exec_path}\\web_replay\\set_args.ps1 {web_replay_ps1_args}"
            ], expected_exit_code="")

            if Params.getCalculated("last_call_exit_code") != "0":
                err_info = "Specified browser does not appear to be pinned to taskbar"
                logging.error(err_info)
                self.fail(err_info)


    def _web_replay_remote_server_start(self, archive_file, theme):
        version = self.web_replay_version

        launch_cmd = f"C:\\web_replay\\{version}\\launch_web_replay.ps1 -Version {version} -Theme {theme}"
        launch_cmd += f" -Archive {archive_file} -Excludes '{self.web_replay_excludes_list}'"

        if self.web_replay_rand_ports == "0":
            launch_cmd += f" -RandPorts 0 -HttpPort {self.web_replay_http_port} -HttpsPort {self.web_replay_https_port}"

        return rpc.call_rpc(self.web_replay_ip, 6000, "RunWithResultAndExitCode", ["powershell", launch_cmd], timeout = 60)


    def _web_replay_find_free_port(self):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            return str(s.getsockname()[1])


    def _web_replay_check_log(self, youtube_duration):
        if Params.get("global", "web_replay_check_enable") == "0":
             logging.warning("Web replay log check is disabled")
             return
        # Sleep 30min for web http connections to timeout
        if self.web_replay_run == '0' and self.web_replay_action == "netlog":
            idle_sleep = 1800

            logging.info(f"Sleeping for {idle_sleep}s for http connections to timeout")
            time.sleep(idle_sleep)

        if self.web_replay_run == '0':
            return

        try:
            requests.get(
                f'http://{self.web_replay_ip}:{self.web_replay_http_port}/web-page-replay-save-log'
            )
        except Exception as e:
            raise e

        log_dir = os.path.join(self.result_dir, 'web_replay')
        log_data = {}

        if self.web_replay_action != "replay" or not os.path.isdir(log_dir):
            return log_data

        for fname in os.listdir(log_dir):
            if not fname.endswith('.json'):
                continue

            with open(os.path.join(log_dir, fname), 'r') as f:
                log_data[os.path.splitext(fname)[0]] = json.load(f)

        for yt_entry in log_data.get("youtube", []):
            title = yt_entry["title"]
            dur = yt_entry["end"] - yt_entry["start"]

            logging.debug(f"Checking YouTube playback log entry '{title}'.  Comparing expected duration {youtube_duration}s with actual duration {dur:.2f}s")
            if not youtube_duration - 15 <= dur <= youtube_duration + 15:
                err_str = f"Unexpected YouTube {title} playback duration {dur}"
                logging.error(err_str)
                self.fail(err_str)


    def _web_replay_change_archive(self, next_name):
        if self.web_replay_run == '0':
            return

        try:
            requests.get(
                f'http://{self.web_replay_ip}:{self.web_replay_http_port}/web-page-replay-change-archive?n={next_name}'
            )
        except Exception as e:
            raise e


    def _web_replay_download(self, archive_file):
        version = self.web_replay_version

        github_download = "https://github.com/microsoft/web_replay/releases/download"
        archive_file_basename = os.path.basename(archive_file)

        url_binary      = f"{github_download}/{version}/web_replay.zip"
        target_binary   = f"C:\\web_replay\\{version}"
        zip_file_binary = f"{target_binary}\\web_replay.zip"

        url_archive      = f"{github_download}/archive-1/{archive_file_basename}.zip"
        target_archive   = archive_file
        zip_file_archive = f"{target_archive}\\archive.zip"

        lock = f"{target_binary}\\web_replay.lock"
        for count in range(1000):
            try:
                os.makedirs(lock)
                break
            except:
                time.sleep(5)
        if count >= 1000:
            raise Exception(f"Timeout trying to acquire lock: {lock}")

        def download_zip(zip_file, url, target):
            try:
                with open(zip_file, 'wb') as f:
                    f.write(requests.get(url).content)

                with zipfile.ZipFile(zip_file, 'r') as f:
                    f.extractall(target)
            finally:
                os.remove(zip_file)
                if len(os.listdir(target)) == 0:
                    os.rmdir(target)

        try:
            if not os.path.exists(f"{target_binary}\\bin"):
                os.makedirs(target_binary, exist_ok=True)
                os.makedirs(f"{target_binary}\\recordings", exist_ok=True)
                download_zip(zip_file_binary, url_binary, target_binary)
                logging.info("Downloaded web_replay binary")

            if self.web_replay_action == "replay" and not \
            (os.path.isfile(target_archive) or os.path.isdir(target_archive)):
                os.makedirs(target_archive, exist_ok=True)
                download_zip(zip_file_archive, url_archive, target_archive)
                logging.info(f"Downloaded {archive_file_basename} archive")
        finally:
            os.rmdir(lock)


    def _web_replay_firewall_check(self, version):
        if self.web_replay_ip != self.host_ip:
            # No need to check firewall on the remote server
            return

        self._host_call("powershell.exe unblock-file -path .\\utilities\\open_source\\web_replay\\firewall_check.ps1")
        self._host_call("powershell.exe unblock-file -path .\\utilities\\open_source\\web_replay\\firewall_add.ps1")

        out = self._host_call(
            f"powershell.exe -File .\\utilities\\open_source\\web_replay\\firewall_check.ps1 -Version {version}"
        )

        if out == "":
            return

        consent = self._host_call(
            "powershell.exe (Get-ItemProperty -Path HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System).ConsentPromptBehaviorAdmin"
        )

        add_log = "Adding firewall entry for web_replay"

        if consent == "0":
            logging.info(add_log)
        else:
            logging.info(f"{add_log}. WARNING: UAC prompt may show up")

        self._host_call(
            f"powershell.exe -File .\\utilities\\open_source\\web_replay\\firewall_add.ps1 -Version {version}"
        )


    def _web_replay_cookies_remove(self):
        version = self.web_replay_version

        if self.web_replay_recording == '':
            raise Exception("web_replay recording archive not specified")

        if os.path.isabs(self.web_replay_recording):
            archive_file = self.web_replay_recording
        else:
            archive_file = f'C:\\web_replay\\{version}\\recordings\\{self.web_replay_recording}'

        if not os.path.isfile(archive_file):
            raise Exception(f"Archive {archive_file} invalid")

        logging.info(f"Removing cookies from {archive_file}")

        archive_exe = f"C:\\web_replay\\{version}\\bin\\archive.exe"
        web_replay_cmd = f'{archive_exe} cookiesRemove {archive_file} {archive_file} > NUL 2>&1'

        self._host_call(web_replay_cmd, cwd = f'C:\\web_replay\\{version}')


    def _web_replay_idle_timeout(self):
        version = self.web_replay_version

        if self.web_replay_recording == '':
            raise Exception("web_replay recording archive not specified")

        if os.path.isabs(self.web_replay_recording):
            archive_file = self.web_replay_recording
        else:
            archive_file = f'C:\\web_replay\\{version}\\recordings\\{self.web_replay_recording}'

        idle_timeouts_file = f'C:\\web_replay\\{version}\\recordings\\idle_timeouts.json'

        logging.info(f"Using server idle timeouts file {idle_timeouts_file}")
        logging.info(f"Adding server idle timeouts to {archive_file}")

        archive_exe = f"C:\\web_replay\\{version}\\bin\\archive.exe"
        out_file = os.path.join(self.result_dir, 'archive.log')

        web_replay_cmd = f'{archive_exe} idleTimeout {archive_file} {idle_timeouts_file} {archive_file} > {out_file} 2>&1'

        self._host_call(web_replay_cmd, cwd = f'C:\\web_replay\\{version}')
    
    def _run_with_inputinject(self, command):
        '''Runs a command on the remote DUT using InputInject to send a win+r to bring up the run dialog, and then typing out the command to run. Useful for platforms like w365.'''
        if self.platform.lower() != "w365" and self.platform.lower() != "windows":
            raise Exception("run_with_inputinject is only supported on W365/windows platform")
        if not command:
            raise Exception("Command to run with InputInject cannot be empty")

        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", "\ue03dr", 50) # Open the run dialog
        time.sleep(3)  # Wait for the run dialog to appear
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", "\ue003", 50) # Clear any previous input
        time.sleep(3)  # Wait for the input to clear
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", command, 50) # Type the command
        time.sleep(3)  # Wait for the command to be typed
        rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", "\ue007", 50) # Press Enter to execute the command
        time.sleep(5)  # Wait for the command to execute


        


class thread_with_exception(threading.Thread):
    def __init__(self, name, method, exceptionEvent, threadEvent, args=None, rundown='0'): 
        threading.Thread.__init__(self) 
        self.name = name 
        self.args = args
        self.entryMethod = method
        self.exceptionEvent = exceptionEvent
        self.threadEvent = threadEvent
        self.rundown = rundown
        self.result = ""
        self.errormsg = ""
              
    def run(self): 
        try: 
            # target function of the thread class 
            if self.args is None:
                self.result = self.entryMethod()
            else:
                self.result = self.entryMethod(*self.args)
        # propagate any exceptions to calling thread
        except Exception as e :
            # Set exception event
            self.exceptionEvent.set()
            # logging.error("Exception in secondary thread!")
            if("Device monitor timeout" in str(e)):
                logging.info('Device entered hibernate')
            else:
                if self.rundown == '0':
                    logging.error(e)
                    self.errormsg = traceback.format_exc()
                else:
                    logging.debug("scenario rundown debug error log")
                    logging.debug(traceback.format_exc())

            # raise e   
        # logging.debug("Thread complete")
        self.threadEvent.set()

    def get_id(self): 
  
        # returns id of the respective thread 
        if hasattr(self, '_thread_id'): 
            return self._thread_id 
        for id, thread in threading._active.items(): 
            if thread is self: 
                return id
   
    def raise_exception(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit)) 
         
        if res > 1: 
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0) 
            # print('Exception raise failure') 
        
    def force_exception(self):
        sys.exit()

