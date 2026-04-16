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

    # UTC side-load and DiagTrack restart are handled by Phase 1 in perf_stress.py setUp().
    # This code block only needs to upload stress scripts and start the stress workload.
    # Registry settings for telemetry are also set in Phase 1.

    src_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(src_dir, "..", "..", ".."))
    dut_bin_dir = r"C:\hobl_bin"

    files_to_upload = [
        os.path.join(src_dir, "percentile_stress.py"),
        os.path.join(src_dir, "rightClick_context_menu.ps1"),
        os.path.join(src_dir, "stop_perfStress_background.ps1"),
    ]

    scenario._remote_make_dir(dut_bin_dir)
    for src_file in files_to_upload:
        if not os.path.isfile(src_file):
            scenario.fail(f"Required file missing: {src_file}")
        logging.info(f"Uploading to DUT {dut_bin_dir}: {src_file}")
        scenario._upload(src_file, dut_bin_dir)

    # Upload cs_floor_wrapper.cmd and sleep.exe to subdirectories matching cs_floor scenario
    scenario._upload(os.path.join(repo_root, "scenarios", "windows", "cs_floor", "cs_floor_wrapper.cmd"),
                     os.path.join(dut_bin_dir, "cs_floor_resources"))
    scenario._upload(os.path.join(repo_root, "utilities", "proprietary", "sleep", "sleep.exe"),
                     os.path.join(dut_bin_dir, "sleep"))

    # Start stress script in background so scenario can proceed.
    # Uses pyenv python if available, otherwise falls back to system python.
    # (Trace collection is handled by the early code_PSECTRC.py block.)
    stress_py = rf"{dut_bin_dir}\percentile_stress.py"
    target_cpu = Params.get('perf_stress', 'stress_cpu_target')
    if target_cpu not in ['25', '50', '65', '75', '85']:
        target_cpu = '75'
    load_label = {
        '25': 'low',
        '50': 'medium',
        '65': 'medium-high',
        '75': 'high',
        '85': 'very high',
    }.get(target_cpu, 'high')
    logging.info(f"Starting percentile_stress.py in minimized window with target CPU {target_cpu}% ({load_label} load).")
    # Use pyenv python if available (matches pytorch_inf pattern), fallback to py/python
    scenario._call([
        "cmd.exe",
        f'/C start "" /min cmd.exe /c "pyenv which python > nul 2>&1 && (for /f \"delims=\" %P in (\'pyenv which python\') do \"%P\" \"{stress_py}\" --target-cpu {target_cpu}) || (where py > nul 2>&1 && py -3 \"{stress_py}\" --target-cpu {target_cpu} || python \"{stress_py}\" --target-cpu {target_cpu})"',
    ], expected_exit_code="", blocking=False)

    scenario._sleep_to_now()
            