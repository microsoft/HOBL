# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
from parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1EN194J.py')

    if Params.get('perf_stress', 'stress_run') != '1':
        logging.info('Skipping background trace/stress scripts because stress_run is disabled')
        return

    # UTC side-load and telemetry service restart are handled by Phase 1 in perf_stress.py setUp().
    # This code block only needs to upload stress scripts and start the stress workload.
    # Registry settings for telemetry are also set in Phase 1.

    src_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(src_dir, "..", "..", ".."))
    dut_bin_dir = r"C:\hobl_bin"

    files_to_upload = [
        os.path.join(src_dir, "percentile_stress.py"),
        os.path.join(src_dir, "start_percentile_stress.ps1"),
        os.path.join(src_dir, "stop_perfStress_background.ps1"),
        os.path.join(src_dir, "collect_5min_traces.ps1"),
        os.path.join(repo_root, "providers", "general_cpi_collector.wprp"),
    ]

    scenario._remote_make_dir(dut_bin_dir)
    for src_file in files_to_upload:
        if not os.path.isfile(src_file):
            scenario.fail(f"Required file missing: {src_file}")
        logging.info(f"Uploading to DUT {dut_bin_dir}: {src_file}")
        scenario._upload(src_file, dut_bin_dir)

    # NOTE: button.exe and the button kernel driver are installed by the
    # 'button_install' prep scenario (see PerfStress.prep_scenarios). It handles
    # arch selection (x64/arm64), uploads to C:\hobl_bin\button, and runs
    # 'button.exe -i' to install the .sys/.inf/.cat driver. We just consume the
    # installed binary in code_PSECSLP1.py via 'button.exe -s <ms>'.

    # Start stress script in background so scenario can proceed.
    # Uses pyenv python if available, otherwise falls back to system python.
    # (Trace collection is handled by the early code_PSECTRC.py block.)
    stress_py = rf"{dut_bin_dir}\percentile_stress.py"
    target_cpu = Params.get('perf_stress', 'stress_cpu_target')
    if target_cpu not in ['0', '25', '50', '65', '75', '85']:
        target_cpu = '75'

    if target_cpu == '0':
        logging.info('stress_cpu_target=0%, skipping percentile_stress.py (no CPU stress).')
        scenario._sleep_to_now()
        return

    load_label = {
        '25': 'low',
        '50': 'medium',
        '65': 'medium-high',
        '75': 'high',
        '85': 'very high',
    }.get(target_cpu, 'high')
    logging.info(f"Starting percentile_stress.py in minimized window with target CPU {target_cpu}% ({load_label} load).")
    # Delegate launch to start_percentile_stress.ps1 on the DUT.
    # Modular by design: that script owns pyenv resolution, python.exe discovery,
    # diagnostic logging to C:\hobl_bin\percentile_stress_launch.log, and the
    # post-launch liveness check. Works identically on x64 and arm64 DUTs because
    # pyenv-win itself selects the right python build during prep.
    # We run BLOCKING so the launcher's Write-Host output streams back via the
    # 'Run' RPC and we can re-log it host-side. The inner Start-Process backgrounds
    # python.exe so the launcher itself returns in <2s.
    launcher = rf"{dut_bin_dir}\start_percentile_stress.ps1"
    launch_args = (
        f'-NoProfile -ExecutionPolicy Bypass -File "{launcher}" '
        f'-ScriptPath "{stress_py}" -TargetCpu {target_cpu}'
    )
    launch_out = scenario._call(
        ["powershell.exe", launch_args],
        expected_exit_code="",
        fail_on_exception=False,
    )
    confirmed = False
    if launch_out:
        for line in str(launch_out).splitlines():
            if line.strip():
                logging.info(f"  launcher: {line.rstrip()}")
                if 'PERCENTILE_STRESS_RUNNING' in line:
                    confirmed = True
    if confirmed:
        logging.info('percentile_stress.py confirmed running on DUT.')
    else:
        logging.warning(' WARNING - percentile_stress.py launch not confirmed; '
                        'CPU stress may not be applied this run. '
                        'See C:\\hobl_bin\\percentile_stress_launch.log on DUT for details.')

    scenario._sleep_to_now()
            