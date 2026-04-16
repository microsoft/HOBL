# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import importlib
import sys
import os
from pathlib import Path

f_path = Path(__file__).resolve()
p_dir  = str(f_path.parent)
pp_dir = str(f_path.parents[1])
os.chdir(pp_dir)
if p_dir in sys.path:
    sys.path.remove(p_dir)
sys.path.insert(0, pp_dir)
import core.alias_finder

if ("-e" in sys.argv):
    index = sys.argv.index('-e')
    script = sys.argv[index+1]
    sys.argv.remove(script)
    sys.argv.remove("-e")
    exe_module = importlib.import_module(script)
    exe_module.main()
    sys.exit(0)

import core.arguments
from core.parameters import Params
from utilities.open_source.modules import get_parent_modules

if "-d" not in sys.argv and "-dv" not in sys.argv:
    import shutil
    import glob
    import subprocess
    import inspect
    import time
    import core.call_rpc as rpc
    import socket
    import requests
    import traceback
    import datetime
    import logging
    import unittest
    import stat

    from urllib.parse import (
        urlparse,
        urlunparse
    )

    from utilities.open_source.scenario_type import scenario_type
    from utilities.open_source.email_notify import send_fail_email

params = Params

# Set default global parameters
params.setDefault('global', 'hardware_version', '', desc="Optional information to pass to reporting.")
params.setDefault('global', 'accessories', '', desc="Optional information to pass to reporting.")
params.setDefault('global', 'result_dir', 'c:\\hobl_results', desc="Base file path for storing test results.")
params.setDefault('global', 'goals', '', desc="Path to a CSV file that has goals for each scenario to compare results with.")
params.setDefault('global', 'charge_on_call', '', desc="A shell command to turn on an attached charger.") 
params.setDefault('global', 'charge_off_call', '', desc="A shell command to turn off an attached charger.") 
params.setDefault('global', 'browser', 'Edge', desc="Web browser to use.", valOptions=["Edge", "Edge Beta", "Edge Dev", "Edge Canary", "Chrome"])
params.setDefault('global', 'host_ip', '', desc="Option to override IP address of host computer, if it doesn't get automatically determined properly.")  # Will try to determine automatically if blank
params.setDefault('global', 'run_type', '', desc="A results sub-folde to indicate the type of run it is, such as 'Power', 'ETL', 'Misc', etc.")
params.setDefault('global', 'iterations', '1', desc="How many time to repeat the scenario.")
params.setDefault('global', 'training_mode', '0', desc="Specify if this is a training run (1) or not (0).", valOptions=["0", "1"])
params.setDefault('global', 'platform', 'Windows', desc="Operating system platform.", valOptions=["Windows", "Android", "W365", "MacOS"])
params.setDefault('global', 'msa_account', '', desc="The test account that Windows and apps will be logged in with.")
params.setDefault('global', 'dut_password', '', desc="The password for the test account (msa_account).")
params.setDefault('global', 'dut_ip', '127.0.0.1', desc="IP address of the Device Under Test (name can be used if DNS is supported).")
params.setDefault('global', 'dut_name', '', desc="Name of the Device Under Test.  Every DUT on the lab netowrk needs to have a unique name.")
params.setDefault('global', 'dut_architecture', 'x64', desc="The CPU architecture of the DUT, used for running apps and tools that are optimized for that architecture.", valOptions=["x64", "arm64"])
params.setDefault('global', 'dut_wifi_name', '', desc="Name of the Wi-Fi netowrk SSID that this device should connect to.")
params.setDefault('global', 'dut_wifi_password', '', desc="Password of the Wi-Fi netowrk SSID that this device should connect to.")
params.setDefault('global', 'dut_wifi_authentication', 'WPA2PSK', desc="Wi-Fi authentication type.", valOptions=["WPA2PSK", "WPA3SAE"]) # WPA3SAE for Wi-Fi 6E+
params.setDefault('global', 'app_port', '4723', desc="Deprecated.")
params.setDefault('global', 'systemPort', '8200', desc="Deprecated.") # android port for forwarding for uiautomator2
params.setDefault('global', 'web_port', '17556', desc="Deprecated.") # MicrosoftEdgeDriver is 17556, chromedriver is 9515
params.setDefault('global', 'port_range_low', '0', desc="Deprecated.")
params.setDefault('global', 'port_range_high', '0', desc="Deprecated.")
# params.setDefault('global', 'scenarios', 'timer')
params.setDefault('global', 'config_check', '1', desc="Enable running config_check (1) or not (0).", valOptions=["1", "0"])
params.setDefault('global', 'callback_test_begin', '', desc="Shell command to call when test measurement phase begins.")
params.setDefault('global', 'callback_test_end', '', desc="Shell command to call when test measurement phase ends.")
params.setDefault('global', 'callback_data_ready', '', desc="Shell command to call when data has been copied back from the DUT.")
params.setDefault('global', 'callback_test_fail', '', desc="Shell command to call when a test fails, to reset any instruments.")
params.setDefault('global', 'collection_enabled', '1', desc="Enable data collection from the test scenarip (1) or not (0).", valOptions=["1", "0"])
params.setDefault('global', 'post_run_delay', '60', desc="Seconds to pause to let the system quiesce after a scenario.")
params.setDefault('global', 'pre_run_delay', '0', desc="Seconds to pause to let the system quiesce before a scenario.")
# params.setDefault('global', 'power_after', '0') # deprecated
params.setDefault('global', 'module_name', '', desc="Override the name of a scenario, if needed.")
params.setDefault('global', 'attempts', '1', desc="How many times to re-attempt the scenario, in case of failure.")
params.setDefault('global', 'tools', '', desc="Space-separated list of tools to run with each non-prep scenario.")
params.setDefault('global', 'prep_tools', '', desc="Space-separated list of tools to run with each prep scenario.")
params.setDefault('global', 'trace_filemode', '1', desc="Whether to run ETL traces in filemode (1) or memory mode (0).", valOptions=["1", "0"])
params.setDefault('global', 'typing_delay', '200', desc="Milliseconds between injected key strokes.")
params.setDefault('global', 'local_execution', '0')
params.setDefault('global', 'phase_reporting', '0')
params.setDefault('global', 'output_level', 'INFO') # ERROR, DEBUG, INFO
params.setDefault('global', 'study_type', '')
params.setDefault('global', 'dashboard_port', '0')
params.setDefault('global', 'dashboard_url', '')
params.setDefault('global', 'dashboard_plan_id', '0')
params.setDefault('global', 'dashboard_scenario_id', '0')
params.setDefault('global', 'rename_fail', '0')
params.setDefault('global', 'async_comm', '1')
params.setDefault('global', 'sleep_wake_call', '')
params.setDefault('global', 'hard_reboot_call', '')
params.setDefault('global', 'stop_soc', '5')  # Rundown Stop SoC level in percent
params.setDefault('global', 'crit_batt_level', '3')  # Full Rundown SOC threshold level in percent
params.setDefault('global', 'trigger_soc', '5')  # Rundown trigger SoC level in percent to call post config and save etl
params.setDefault('global', 'trigger_script', 'postconfig_etl.bat')  # Rundown trigger script to call post config and save etl
params.setDefault('global', 'rundown_mode', '0')  # Rundown Enable Switch
params.setDefault('global', 'goal_limit', '30') # Goal_limit is a percentage (30%)
params.setDefault('global', 'warn_limit', '20') # Warn_limit is a percentage (20%)
# params.setDefault('global', 'enable_vbs', '')
params.setDefault('global', 'hobl_external', '', desc="External HOBL directories for specifying extra scenarios/tools/utilities", multiple=True)

params.setDefault('global', 'web_replay_run', '0')
params.setDefault('global', 'web_replay_check_enable', '1')
params.setDefault('global', 'web_replay_action', 'replay', desc="Behavior of Web Replay.", valOptions=["record", "replay", "bulk_record", "bulk_replay", "netlog"])
params.setDefault('global', 'web_replay_recording', 'web_archive_2026-04-08')
params.setDefault('global', 'web_replay_rand_ports', '1')
params.setDefault('global', 'web_replay_http_port', '9080')
params.setDefault('global', 'web_replay_https_port', '9081')
params.setDefault('global', 'web_replay_http_proxy_port', '')
params.setDefault('global', 'web_replay_excludes_list', 'edge ntp graph.microsoft.com', desc="Websites to exclude from Web Replay and go live instead.", valOptions=["reddit", "instagram", "amazon", "google", "youtube", "edge"], multiple=True)
params.setDefault('global', 'web_replay_ip', '')

params.setDefault('global', 'sender_email_addr', '')
params.setDefault('global', 'sender_email_password', '')
params.setDefault('global', 'notify_email_list', '')
params.setDefault('global', 'fail_email_list', '')

params.setDefault('global', 'remote_share_path', '')
params.setDefault('global', 'remote_share_username', '')
params.setDefault('global', 'remote_share_password', '')

params.setDefault('global', 'office_theme', "Don't Change", desc="Theme of Office apps.", valOptions=["Don't Change", "System", "Colorful", "Dark Gray", "Black", "White"])
params.setDefault('global', 'product', '')
params.setDefault('global', 'dut_scaling_override', '', desc="Override the scaling factor of the DUT, if it is not reporting correctly.")
params.setDefault('global', 'dut_coord_scaler', '1.0', desc="Multiply InputInject coordinates by this scale factor.")

params.setDefault('global', 'prep_status_enable', '1', desc="Check prep status before scenario execution.", valOptions=["1", "0"])
params.setDefault('global', 'prep_run_only', '0', desc="Run prep only for scenarios that have both a prep and test component.", valOptions=["1", "0"])
params.setDefault('global', 'result_dir_complete', '', desc="Completed file path for storing test results (already including study type, study variables, and run type).")


# Command line arguments
core.arguments.Arguments()
args = core.arguments.args
params_file = args.profile
if params_file is None or params_file == "":
    params_file = "profile_templates\\default.ini"
elif not os.path.exists(params_file):
    print("ERROR:  Specified device profile path does not exist: " + params_file)
    sys.exit(1)
# print("Using profile: " + params_file)
params.setCalculated("params_file", params_file)

cmd_tests = args.scenarios
kill_test = args.kill
# pc_test = args.prep_check

# Dump default args, if specified
if args.dump or args.dump_verbose:
    Params("")
    Params.setOverrides(args.overrides)

    if args.dump_verbose:
        scenarios = args.dump_verbose.split()
    else:
        scenarios = args.dump.split()

    hobl_ext_paths = params.get('global', 'hobl_external', log = False).split()
    sys.path[1:1] = hobl_ext_paths

    parent_modules = get_parent_modules(
        ["scenarios", "tools"],
        ext_paths=hobl_ext_paths
    )

    for scenario in scenarios:
        if "global" not in scenario:
            for parent_module in parent_modules:
                try:
                    importlib.import_module(
                        f'{parent_module}.{scenario}'
                    )
                    break
                except:
                    pass

    if args.dump_verbose:
        params.dumpDefaultWithInfo()
    else:
        params.dumpDefault()

    sys.exit(0)

# Check if we're runnign a scenario that shouldn't contact the DUT before
# loading params, which can make calls to the DUT
for scenario in ['charge_off', 'charge_on', 'hard_reboot', 'sleep_wake', 'manual_offline', 'study_report', 'run_report', 'dut_setup']:
    if scenario in sys.argv:
        print("Forcing dut_alive to 0")
        Params.setCalculated("dut_alive", '0')

# Load parameters
Params(params_file)
Params.setOverrides(args.overrides)

hobl_ext_paths = params.get('global', 'hobl_external', log = False).split()
dut_ip = params.get('global', 'dut_ip', log = False)
local_execution = params.get('global', 'local_execution', log = False)

sys.path[1:1] = hobl_ext_paths

if Params.getCalculated("dut_alive") != '0':
    # if local_execution == "0" and params.get('global', 'platform').lower() == 'windows':
    if local_execution == "0":
        # Check if DUT is alive by pinging Simple Remote
        try:
            print(datetime.datetime.now(), "INFO Checking if DUT is alive...")
            rpc.call_rpc(dut_ip, 8000, "GetVersion", [], log=False, timeout = 5)
            Params.setCalculated("dut_alive", '1')
            print(datetime.datetime.now(), "INFO It is.")
        except:
            try:
                print(datetime.datetime.now(), "INFO Checking again if DUT is alive...")
                rpc.call_rpc(dut_ip, 8000, "GetVersion", [], log=False, timeout = 10)
                Params.setCalculated("dut_alive", '1')
                print(datetime.datetime.now(), "INFO It is.")
            except:
                # DUT is not alive
                Params.setCalculated("dut_alive", '0')
                print(datetime.datetime.now(), "INFO It is not.")
    else:
        # Assume DUT is alive for local exection
        Params.setCalculated("dut_alive", '1')

run_type = "Power"
if any(scenario_type((cmd_tests or "").split(), hobl_ext_paths).values()):
    run_type = "Prep"

base_result_dir = params.get('global', 'result_dir', log = False)
base_result_dir = base_result_dir.rstrip('\\')

run_type_param = params.get('global', 'run_type', log = False)
if run_type_param != "":
    run_type = run_type_param
study_type = params.get('global', 'study_type', log = False)
if study_type != "":
    study_type = "\\" + study_type
expanded_study_vars = params.expandStudyVars()
study_result_dir = base_result_dir + study_type + expanded_study_vars
result_dir = study_result_dir + "\\" + run_type
result_dir_complete = params.get('global', 'result_dir_complete', log = False)
if result_dir_complete:
    result_dir = result_dir_complete.rstrip('\\')
params.setCalculated("base_result_dir", base_result_dir)
params.setCalculated("study_result_dir", study_result_dir)

dashboard_url = params.get('global', 'dashboard_url')
dashboard_plan_id = params.get('global', 'dashboard_plan_id')
dashboard_scenario_id = params.get('global', 'dashboard_scenario_id')


class StreamHandlerWrapper(logging.StreamHandler):
    is_error_seen = False

    def emit(self, record):
        super().emit(record)

        if record.levelno == logging.ERROR and not type(self).is_error_seen:
            if dashboard_url != '':
                url = urlunparse(
                    urlparse(dashboard_url)._replace(
                        path="/plan/ScenarioErrorReceived"
                    )
                )

                requests.post(
                    url,
                    {
                        "scenarioId": int(dashboard_scenario_id),
                        "errorInfo": record.message
                    }
                )

            type(self).is_error_seen = True


def open_log(log=None):
    if log:
        logging.basicConfig(filename=log, filemode='w', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(module)s:%(lineno)d  %(message)s')
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(module)s:%(lineno)d  %(message)s')
        return
    global root
    root = logging.getLogger()
    ch = StreamHandlerWrapper(sys.stdout)
    output_level = params.get('global', 'output_level', log = False)
    dashboard_url = params.get('global', 'dashboard_url')
    # If dashboard (HOBL UI) is being used, force debug output
    if dashboard_url != '':
        output_level = "DEBUG"

    if output_level == "DEBUG":
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s:%(lineno)d  %(message)s', "%Y-%m-%d %H:%M:%S")
    elif output_level == "ERROR":
        ch.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s:%(lineno)d  %(message)s', "%Y-%m-%d %H:%M:%S")
    else:
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', "%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    root.addHandler(ch)


def close_log():
    global root
    handlers = root.handlers[:]
    for handler in handlers:
        handler.close()
        root.removeHandler(handler)


def set_run_dir(module):
    suffix = 0
    if params.get("global", "training_mode") == '1' or "training" in module:
        if params.get('global', 'module_name') != '':
            module = params.get('global', 'module_name') 
        if "training" in module:
            test_name = module + "_{:03d}".format(suffix)
            run_dirs = os.path.join(base_result_dir+"\\Training", module) + "_[0-9][0-9][0-9]*"
        else:
            test_name = module + "_training" + "_{:03d}".format(suffix)
            run_dirs = os.path.join(base_result_dir+"\\Training", module) + "_training_[0-9][0-9][0-9]*"
        run_dir = os.path.join(base_result_dir+"\\Training", test_name)

        # Get largest suffix in list of run directories
        l = len(run_dir)
        suffixes = [dir[l-3:l] for dir in glob.glob(run_dirs)]
        if len(suffixes) > 0:
            max_suffix = max(suffixes)
            suffix = int(max_suffix) + 1

        if "training" in module:
            test_name = module + "_{:03d}".format(suffix)
        else:
            test_name = module + "_training" + "_{:03d}".format(suffix)

        run_dir = os.path.join(base_result_dir+"\\Training", test_name)
    elif "after" in module:
        test_name = params.get('global', 'module_name')
        if (test_name == ""):
            test_name = "after"
        run_dir = os.path.join(result_dir, test_name)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
    else:
        if params.get('global', 'module_name') != '':
            module = params.get('global', 'module_name') 
        test_name = module + "_{:03d}".format(suffix)
        # base_run_dir = params.get('global', 'result_dir')
        run_dir = os.path.join(result_dir, test_name)
        run_dirs = os.path.join(result_dir, module) + "_[0-9][0-9][0-9]*"
        # Get largest suffix in list of run directories
        l = len(run_dir)
        suffixes = [dir[l-3:l] for dir in glob.glob(run_dirs)]
        if len(suffixes) > 0:
            max_suffix = max(suffixes)
            suffix = int(max_suffix) + 1
        test_name = module + "_{:03d}".format(suffix)
        run_dir = os.path.join(result_dir, test_name)
    time.sleep(1)
    if not os.path.exists(run_dir):
        os.makedirs(run_dir)
    
    params.setCalculated("run_dir", run_dir)
    params.setCalculated("test_name", test_name)
    # print "RUN DIR", run_dir
    # print "TEST_NAME", test_name

    # Copy profile to run dir
    # shutil.copy(args.profile, run_dir)
    # shutil.copy(params_file, run_dir)
    


def host_call(command, cwd = "."):
    logging.debug("Calling: " + command)
    p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = True, cwd = cwd)
    out, err = p.communicate()
    if len(out) > 0:
        for line in out.split(b'\n'):
            l = line.decode().strip("\r\n")
            if l:
                logging.debug(l)
    if len(err) > 0:
        for line in err.split(b'\n'):
            l = line.decode().strip("\r\n")
            if l:
                logging.error(l)
    return(out.decode().strip("\r\n"))


def kill(test_name):
    kill_module_str = get_test_module(test_name, hobl_ext_paths)
    params.setCalculated("kill_mode", "1")
    print(f"Kill module: {kill_module_str}")
    kill_module = importlib.import_module(kill_module_str)
    for name, obj in inspect.getmembers(kill_module, lambda member: inspect.isclass(member) and kill_module_str in member.__module__):
        if "Thread" in name:
            continue
        kill_class_str = name
        kill_class = getattr(kill_module, kill_class_str)
        kill_instance = kill_class()
        print("Calling kill()")
        kill_instance.kill_wrapper()


def prep_check(test_name):
    pc_module_str = get_test_module(test_name, hobl_ext_paths)
    pc_module = importlib.import_module(pc_module_str)
    for name, obj in inspect.getmembers(pc_module, lambda member: inspect.isclass(member) and pc_module_str in member.__module__):
        if "Thread" in name:
            continue
        pc_class_str = name
        pc_class = getattr(pc_module, pc_class_str)
        pc_instance = pc_class()

        # Create CLient server
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            dashboard_port = params.get('global', 'dashboard_port')
            # Connect to server and send send_msg
            skt.connect(("localhost", int(dashboard_port)))
            skt.sendall("na".encode('utf-8'))
        except:
            pass
        finally:
            skt.close()

        # Run check
        pc_instance.prepCheck()


def write_desktop_ini(path, status):
    output = host_call(r"cmd /C utilities\open_source\UpdateIcon\UpdateIcon.exe " + path + " " + status)
    if output == "0":
        return
    else:
        # Most likely failure of UpdateIcon is that .net runtime is not installed, so install it.
        print ("Installing dotnet runtime")
        host_call(r"cmd /C setup\src\dotnet-runtime-6.0.7-win-x86.exe /quiet")
        time.sleep(15)
        # Then try again
        host_call(r"cmd /C utilities\open_source\UpdateIcon\UpdateIcon.exe " + path + " " + status)


def get_test_module(test_name, ext_paths=[]):
    parent_modules = get_parent_modules(["scenarios"], ext_paths=ext_paths)
    test_module = "scenarios.common.scenario_invalid"
    params.setCalculated("scenario_invalid", test_name + " does not exist")

    for parent_module in parent_modules:
        module = f"{parent_module}.{test_name}"

        try:
            if importlib.util.find_spec(module) is not None:
                test_module = module
                break
        except:
            pass

    # Check platform compatibility
    platform = params.get('global', 'platform', log = False).lower()

    for folder_name, display_name in [("macos", "MacOS"), ("windows", "Windows")]:
        if folder_name in test_module.lower() and platform != folder_name:
            test_module = "scenarios.common.scenario_invalid"
            params.setCalculated("scenario_invalid", f"Invalid platform for {test_name}. Expected platform: {display_name}.")
            break
    
    return test_module


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())
    
    def flush(object):
        pass


class TextTestResult(unittest.TextTestResult):
    def addError(self, test, err):
        super().addError(test, err)
        self._log_exception(test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._log_exception(test, err)

    def _log_exception(self, test, err):
        if StreamHandlerWrapper.is_error_seen:
            return

        trace   = traceback.extract_tb(err[2])
        include = False

        modified_trace = []

        for frame in trace:
            if "unittest" not in frame.filename:
                include = True

            if include:
                modified_trace.append(frame)

        if len(modified_trace) == 1:
            modified_trace.append(modified_trace[0])

        test.logErrorMessages(
            err[1],
            trace=traceback.StackSummary.from_list(modified_trace).format()
        )

def _add_python_embed_firewall():
    firewall_add_cmd = ".\\setup_src\\src_host\\firewall_add.ps1"

    def call(cmd):
        p = subprocess.Popen(cmd, shell = True, cwd = ".")
        p.communicate()

    call(f"powershell.exe unblock-file -path {firewall_add_cmd}")
    call(f"powershell.exe Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser")
    call(f"powershell.exe -File {firewall_add_cmd}")


def send_completion_notification():
    logging.info(f"Posting state Complete to dashboard.")
    while True:
        try:
            response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "State": "Complete"})
            status_code = str(response.status_code)
        except:
            status_code = ""
        if status_code == "200":
            break
        logging.debug(f"Posting Complete, status=" + status_code)
        time.sleep(5)


def send_status_notification(status):
    logging.info(f"Posting status {status} to dashboard.")
    while True:
        try:
            response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "Status": status})
            status_code = str(response.status_code)
        except:
            status_code = ""
        if status_code == "200":
            break
        logging.debug(f"Posting {status}, status=" + status_code)
        time.sleep(5)


def send_pass_notification():
    send_status_notification("PASS")


def send_fail_notification():
    send_status_notification("FAIL")


def preps_missing_print(prep_scenarios_to_run):
    for p in prep_scenarios_to_run:
        if isinstance(p, tuple):
            if isinstance(p[1], list):
                logging.error(f"Missing prep: {p[0]} version = file dependencies")
            else:
                logging.error(f"Missing prep: {p[0]} version = {p[1]}")
        else:
            logging.error(f"Missing prep: {p}")


if __name__ == '__main__':

    try:
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
    except:
        print(" ERROR - Could not create result directory: " + result_dir)
        send_fail_notification()
        send_completion_notification()
        sys.exit(1)

    _add_python_embed_firewall()

    temp_dir = os.getenv('LOCALAPPDATA') + "\\HOBL"

    # if -k <scenario> was specified on the command line, call the kill() method of
    # the specified secenario to kill all processes associated with that scenario on the DUT
    if kill_test != None:
        open_log()
        org_collection = params.get('global', 'collection_enabled')
        params.setOverride("global", "collection_enabled", "0")
        # run_dir = temp_dir + "\\temp_" + os.path.basename(args.profile).replace(".ini", "")
        run_dir = temp_dir + "\\temp_" + os.path.basename(params_file).replace(".ini", "")
        set_run_dir(run_dir)

        # Start Appium server
        if params.get('global', 'platform').lower() == 'android':
            logging.info("Remove DUT port forwarding")
            host_call("adb -s " + dut_ip + ":5555 forward --remove tcp:" + str(params.get('global', 'systemPort'))) # remove port forwarding for uiautomator port on DUT
            logging.info("Looking for Appium")
            # Start Appium server on app_port
            if not shutil.which("appium"):
                logging.info("appium not found, attempting full path launch")
                command = 'cmd.exe /c "C:\\Android\\Appium\\appium.cmd" -p ' + str(params.get('global', 'app_port')) 
                logging.info("Starting Appium Server")
                subprocess.Popen(command)
            else:
                command = "cmd.exe /c appium -p " + str(params.get('global', 'app_port')) + str(params.get('global', 'app_port'))
                logging.info("Starting Appium Server")
                subprocess.Popen(command)
            time.sleep(2)

        kill(kill_test)

        # Call test_fail callback, for things like resetting the DAQ
        if params.get('global', 'callback_test_fail') != "" and params.get('global', 'training_mode') != '1' and org_collection != '0':
            host_call(params.get('global', 'callback_test_fail') + " " + os.path.abspath(run_dir))

        # Stop the Appium Server
        if params.get('global', 'platform').lower() == 'android':
            # Get the PID of the started server (Node)
            appium_pid = subprocess.run(['powershell.exe', '((Get-NetTCPConnection | Where-Object{$_.LocalPort -like "' + str(params.get('global', 'app_port')) + '"}).OwningProcess)'], capture_output=True, text=True).stdout
            logging.debug("Killing server with PID: " + str(appium_pid))
            subprocess.call(["powershell.exe", "kill -Id " + str(appium_pid)])
        
        if dashboard_url != '':
            while True:
                try:
                    response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "State": "Complete"})
                    status_code = str(response.status_code)
                except:
                    status_code = ""
                if status_code == "200":
                    break
                time.sleep(5)

        sys.exit(0)

    # if pc_test != None:
    #     print("Checking: " + pc_test)
    #     params.setOverride("global", "collection_enabled", "0")
    #     set_run_dir(pc_test)
    #     prep_check(pc_test)
    #     run_dir = params.getCalculated("run_dir")
    #     # print ("Deleting: " + run_dir)
    #     shutil.rmtree(run_dir)
    #     sys.exit(0)

    tests = []
    test_cases = []
    if cmd_tests == None:
        test_case_str = params.get('global', 'scenarios')
        if test_case_str:
            test_cases = test_case_str.split()
    else:
        test_cases = cmd_tests.split()

    max_attempts = params.get('global', 'attempts')

    for t in test_cases:
        try:
            [test_case, iterations] = t.split('*')
        except:
            test_case = t
            iterations = params.get('global', 'iterations')
        tests = [get_test_module(test_case, hobl_ext_paths)]

        if tests:
            suite_success = True
            for iteration in range(int(iterations)):
                for attempt in range(int(max_attempts)):
                    params.setCalculated("kill_mode", "0")
                    set_run_dir(test_case)
                    if params.get('global', 'module_name') == '':
                        params.setDefault('global', 'module_name', test_case)
                    params.setCalculated('scenario_section', test_case)
                    run_dir = params.getCalculated("run_dir")
                    log = os.path.join(run_dir, "hobl.log")
                    open_log(log)
                    open(run_dir + "\\.RUNNING", "w+").close()
                    if dashboard_url != '':
                        # Send Result Dir to dashboard.
                        logging.debug("Post Result Dir to dashboard: " + study_result_dir)
                        while True:
                            try:
                                response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "ResultDir": study_result_dir})
                                status_code = str(response.status_code)
                            except:
                                status_code = ""
                            if status_code == "200":
                                break
                            logging.debug("Posting Result Dir, status=" + status_code)
                            time.sleep(5)

                        # Send RUNNING status to dashboard.
                        logging.debug("Post status RUNNING to dashboard.")
                        while True:
                            try:
                                if attempt == 0:
                                    response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "Status": "RUNNING"})
                                else:
                                    response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "Status": "RUNNING_RETRY"})
                                status_code = str(response.status_code)
                            except:
                                status_code = ""
                            if status_code == "200":
                                break
                            logging.debug("Posting Result Dir, status=" + status_code)
                            time.sleep(5)

                        # Send Run Dir to dashboard
                        logging.debug("Post Run Dir to dashboard: " + run_dir)
                        while True:
                            try:
                                response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "RunDir": run_dir})
                                status_code = str(response.status_code)
                            except:
                                status_code = ""
                            if status_code == "200":
                                break
                            logging.debug("Posting Result Dir, status=" + status_code)
                            time.sleep(5)

                    try:
                        fo = open("hobl_version.txt", "r")
                        hobl_ver = fo.readline(50).strip()
                        fo.close()
                        logging.info ("HOBL Version: " + hobl_ver)
                    except:
                        logging.info ("HOBL Version: Unknown")
                    logging.info("run_dir: " + run_dir)
                    params.get('global', 'host_ip') # just to get it to be set properly before dumping
                    params.dump()

                    # Create CLient server
                    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        dashboard_port = params.get('global', 'dashboard_port')
                        # Connect to server and send send_msg
                        skt.connect(("localhost", int(dashboard_port)))
                        skt.sendall(run_dir.encode('utf-8'))
                    except:
                        pass
                    finally:
                        skt.close()

                    suite = unittest.TestLoader().loadTestsFromNames(tests)
                    Params.setOverrides(args.overrides)
                    for test in suite:
                        # suite should only have 1 test.  Just get the first one.
                        break

                    prep_scenarios_to_run = params.getCalculated("prep_scenarios_to_run")

                    test_name = params.getCalculated("test_name")
                    run_type_name = run_type + "." + test_name

                    if prep_scenarios_to_run:
                        logging.error(f"Failed to load test. Run prep(s) first")
                        preps_missing_print(prep_scenarios_to_run)
                        result = None
                    elif run_type.lower() == "misc" or run_type.lower() == "prep" or run_type.lower() == "training" or len(run_type_name) < 32:
                        # Start Appium server
                        if params.get('global', 'platform').lower() == 'android':
                            logging.info("Remove DUT port forwarding")
                            host_call("adb -s " + dut_ip + ":5555 forward --remove tcp:" + str(params.get('global', 'systemPort'))) # remove port forwarding for uiautomator port on DUT
                            logging.info("Looking for Appium")

                            # Start Appium server on app_port
                            if not shutil.which("appium"):
                                logging.info("appium not found, attempting full path launch")
                                command = 'cmd.exe /c "C:\\Android\\Appium\\appium.cmd" -p ' + str(params.get('global', 'app_port')) + " >> " + str(run_dir) + "\\appium.log"
                                logging.debug(command)
                                logging.info("Starting Appium Server")
                                subprocess.Popen(command)
                            else:
                                command = "cmd.exe /c appium -p " + str(params.get('global', 'app_port')) + " >> " + str(run_dir) + "\\appium.log"
                                logging.info("Starting Appium Server")
                                subprocess.Popen(command)
                            time.sleep(2)

                        delay = params.get('global', 'pre_run_delay')
                        if delay != "0":
                            logging.info("Delaying for " + delay + " seconds before run.")
                            time.sleep(int(params.get('global', 'pre_run_delay')))

                        # Run test
                        logging.info("Executing test: " + test_case + ", iteration: " + str(iteration) + ", attempt: " + str(attempt))
                        result = unittest.TextTestRunner(stream=StreamToLogger(logging.getLogger(), logging.INFO), verbosity=0, resultclass=TextTestResult).run(test)
                    else:
                        logging.error("RunType.TestName must be less than 32 characters: " + run_type_name)
                        result = None

                    # Clean up test
                    try:
                        if result is not None: kill(test_case)
                    except:
                        pass
                    
                   # Stop the Appium Server
                    if params.get('global', 'platform').lower() == 'android':
                        # Get the PID of the started server (Node)
                        appium_pid = subprocess.run(['powershell.exe', '((Get-NetTCPConnection | Where-Object{$_.LocalPort -like "' + str(params.get('global', 'app_port')) + '"}).OwningProcess)'], capture_output=True, text=True).stdout
                        logging.debug("Killing server with PID: " + str(appium_pid))
                        subprocess.call(["powershell.exe", "kill -Id " + str(appium_pid)])

                    delay = params.get('global', 'post_run_delay')
                    if delay != "0":
                        logging.info("Delaying for " + delay + " seconds after run.")

                    logging.info("End of log.")
                    # Remove .RUNNING file, will shortly be replaced with .PASS or .FAIL
                    # Note: if terminated from the UI, then UI will remove .RUNNING and write .TERMINATED
                    os.remove(run_dir + "\\.RUNNING")
                    if result and result.wasSuccessful():
                        if dashboard_url != '':
                            # Send PASS notification and write .PASS file.
                            send_pass_notification()
                        open(run_dir + "\\.PASS", "w+").close()
                        # Write desktop.ini file to change Windows File Explorer icon to pass icon
                        write_desktop_ini(run_dir, "pass")
                        success = True

                        try:
                            close_log()
                        except:
                            print("Could not close log.")
                    else:
                        if dashboard_url != '':
                            # Send FAIL notification and write .FAIL file.
                            send_fail_notification()
                        open(run_dir + "\\.FAIL", "w+").close()
                        # Write desktop.ini file to change Windows File Explorer icon to fail icon
                        write_desktop_ini(run_dir, "fail")
                        # Call test_fail callback, for things like resetting the DAQ
                        if params.get('global', 'callback_test_fail') != "" and params.get('global', 'training_mode') != '1' and params.get('global', 'collection_enabled') != '0':
                            host_call(params.get('global', 'callback_test_fail') + " " + os.path.abspath(run_dir))
                        success = False
                        try:
                            close_log()
                        except:
                            print("Could not close log.")
                        if params.get('global', 'rename_fail') == '1':
                            if run_dir != "":
                                fail_dir = run_dir + "_fail"
                                if os.path.exists(fail_dir):
                                    shutil.rmtree(fail_dir)
                                shutil.move(run_dir, fail_dir)

                    print ("Delaying for " + params.get('global', 'post_run_delay') + " seconds after run.")
                    time.sleep(int(params.get('global', 'post_run_delay')))

                    # Update folder timestamp
                    try:
                        if run_dir and run_dir != "":
                            # Update time stamps of all folder from run dir up to root, to support Mercury file transfer
                            path_fields = list(filter(None, run_dir.split('\\')))
                            if len(path_fields) != 0:
                                if run_dir.startswith("\\"):
                                    root = "\\\\" + path_fields[0]
                                else:
                                    root = path_fields[0] + "\\"

                                for i in range(1, len(path_fields)):
                                    root = os.path.join(root, path_fields[i])
                                    os.utime(root)
                            # Also update time stamps of all sub directories
                            for (dirpath, dirnames, filenames) in os.walk(run_dir):
                                for dirname in dirnames:
                                    full_dir_path = os.path.join(dirpath, dirname)
                                    os.utime(full_dir_path)
                    except Exception as e:
                        print(" ERROR update folder timestamp: " + str(e))

                    if result and result.wasSuccessful():
                        break

                if dashboard_url != '':
                    # Send Complete notification
                    while True:
                        try:
                            response = requests.post(dashboard_url, {"PlanID": dashboard_plan_id, "ScenarioID": dashboard_scenario_id, "State": "Complete"})
                            status_code = str(response.status_code)
                        except:
                            status_code = ""
                        if status_code == "200":
                            break   
                        time.sleep(5)

                test_name=params.getCalculated("test_name")
                if params.get('global', 'power_after') == '1' and params.get('global', 'collection_enabled') != '0' and "training" not in test_name:
                    logging.info("Running power between after " + test_name)
                    if "training" not in test_name:
                        test_name_base = test_name[:-4]
                        test_name_index = "_" + test_name[-3:]
                    else:
                        test_name_base = test_name
                        test_name_index = ""

                    subprocess.call(["python.exe", "hobl.py", "-p", params_file, "-s", "after", "global:module_name="+test_name_base+"_after"+test_name_index, "global:power_after=0", "global:run_type="+run_type])
                if success == False:
                    suite_success = False

            if not suite_success:
                send_fail_email(test_case, run_dir, result)

        else:
            logging.error("No test cases specified.")

    # Delete temp run_type
    if run_type == "temp":
        if result_dir and result_dir != "":
            print("Deleting " + result_dir)
            shutil.rmtree(result_dir, onerror=lambda func, path, _: (os.chmod(path, stat.S_IWRITE), func(path)))

    # Checking if local execution and if running from dashboard if so then we want to relaunch the web ui to help notify user that scenario ran. 
    try:
        if dashboard_url != '' and dut_ip == "127.0.0.1":
            subprocess.call(f'start /MAX "" "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --app="http://localhost:80/plan/Scenarios?PlanID={dashboard_plan_id}" --start-maximized', shell=True)
    except:
        pass
    local_execution_reboot_flag = Params.getCalculated("local_execution_reboot")

    if suite_success:
        print("Suite passed")
        if local_execution_reboot_flag == "1":
            # If it's local execution then we need to reboot
            subprocess.call(["shutdown.exe", "/r", "/f", "/t", "5"])
        sys.exit(0)
    else:
        print("Suite failed")
        if local_execution_reboot_flag == "1":
            # If test failed and it's local execution then we want to not reboot and delete the registry key so test can fail and not run into infinite reboots.
            reg_cmd = f'reg.exe DELETE "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v LocalExec_PostReboot /f'
            subprocess.call(["cmd.exe", "/c " + reg_cmd])
        sys.exit(1)
