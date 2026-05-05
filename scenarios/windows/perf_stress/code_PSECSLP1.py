# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import socket
import time

from parameters import Params


def _dut_reachable(ip, port, timeout=1.0):
    """Quick TCP-connect liveness probe. True if DUT's RPC port accepts a connection.
    Avoids importing call_rpc (which isn't on sys.path for code_*.py modules)."""
    try:
        with socket.create_connection((ip, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def run(scenario):
    logging.debug('Executing code block: code_PSECSLP1.py')

    if Params.get('perf_stress', 'sleep_resume_midrun') != '1':
        logging.info('Skipping mid-workload sleep/resume checkpoint because sleep_resume_midrun is disabled')
        return

    # Mid-workload Connected Standby sleep using the same primitive the standby
    # library (_library/misc/standby/code_W33UMT.py) uses: button.exe -s <ms>.
    # We do NOT disconnect Wi-Fi (cs_floor_wrapper.cmd was the wrong tool for
    # this job - per perf-team feedback we want REAL CS so post-resume scenarios
    # exercise the heavy resume overheads, not a 30s Wi-Fi reconnect window).
    #
    # Prereq: 'button_install' is in PerfStress.prep_scenarios so the kernel
    # driver and arch-correct button.exe are already installed at
    # C:\hobl_bin\button\button.exe.
    sleep_duration_seconds = 30

    logging.info(f'Starting mid-workload Connected Standby checkpoint (duration={sleep_duration_seconds}s)')

    button_exe = os.path.join(scenario.dut_exec_path, "button", "button.exe")
    duration_ms = int(sleep_duration_seconds) * 1000
    # 'timeout 3 > NUL' matches the standby library: gives this RPC a moment to
    # return before button.exe puts the DUT into CS.
    cmd_str = f'/C timeout 3 > NUL && "{button_exe}" -s {duration_ms}'
    logging.info(f'DUT command: cmd.exe {cmd_str}')
    try:
        scenario._call(["cmd.exe", cmd_str], blocking=False)
        time.sleep(2)
    except Exception:
        logging.error(" ERROR - button.exe not found on DUT. Run scenarios/windows/button_install "
                      "first, or verify global:dut_architecture in the profile INI.")
        return

    # Probe DUT liveness while waiting so we can detect whether sleep actually
    # happened. button.exe silently no-ops when the kernel driver isn't loaded,
    # so without this probe we'd sleep through the whole window and falsely log
    # "DUT communication restored".
    if Params.get('global', 'local_execution') != '1':
        deadline = time.time() + sleep_duration_seconds + 30
        ever_unreachable = False
        last_alive = True
        logging.info(f'Probing DUT every 2s for up to {sleep_duration_seconds + 30}s to detect sleep')
        while time.time() < deadline:
            alive = _dut_reachable(scenario.dut_ip, scenario.rpc_port)

            if not alive and last_alive:
                logging.info('DUT became unreachable - sleep confirmed')
                ever_unreachable = True
            elif alive and not last_alive:
                logging.info('DUT became reachable again after sleep')
                last_alive = True
                break  # slept and resumed - we're done
            last_alive = alive
            time.sleep(2)

        if not ever_unreachable:
            logging.warning(' WARNING - DUT never became unreachable during the sleep window. '
                            'button.exe likely no-op (kernel driver not installed or wrong '
                            'architecture). Sleep/resume did NOT occur. Verify button_install '
                            'prep ran, and check global:dut_architecture in the profile INI.')

        # Final hard wait for full RPC restoration before returning to scenario.
        scenario._wait_for_dut_comm()
        logging.info('DUT communication restored after sleep/resume checkpoint')

    # Resume immediately into the next action - the whole point of sleep/resume
    # in a stress run is to measure resume-under-stress behavior, so we do not
    # add a quiet settle window here.
    scenario._sleep_to_now()
