# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#
# code_PSECTRC.py - Background rolling heavy WPR capture for perf_stress.
#
# Gated by perf_stress:bg_heavy_capture (default 0). When 1, this:
#   1. Uploads collect_5min_traces.ps1 + general_cpi_collector.wprp to the DUT
#   2. Launches the script in a background minimized window
#   3. The script runs rolling WPR captures on a NAMED instance (perfStressHeavy)
#      so it does NOT collide with HOBL's core unnamed WPR session.
#
# Output ETLs land at C:\WPR_Traces\<runname>\WPR_<timestamp>.etl on the DUT.
#
# CAVEAT: two concurrent WPR sessions perturb perf numbers ~10-30%.
# The PT CSV from this run is for debug use only.

import logging
import os
from parameters import Params


def run(scenario):
    logging.debug('Executing code block: code_PSECTRC.py (background heavy capture)')

    if Params.get('perf_stress', 'stress_run') != '1':
        logging.info('Skipping bg_heavy_capture because stress_run is disabled')
        return

    if Params.get('perf_stress', 'bg_heavy_capture') != '1':
        logging.info('bg_heavy_capture=0 (default) - skipping background WPR capture')
        return

    src_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(src_dir, "..", "..", ".."))
    dut_bin_dir = r"C:\hobl_bin"

    trace_files = [
        os.path.join(src_dir, "collect_5min_traces.ps1"),
        os.path.join(repo_root, "providers", "general_cpi_collector.wprp"),
    ]

    scenario._remote_make_dir(dut_bin_dir)
    for src_file in trace_files:
        if not os.path.isfile(src_file):
            scenario.fail(f"Required file missing: {src_file}")
        logging.info(f"Uploading to DUT {dut_bin_dir}: {src_file}")
        scenario._upload(src_file, dut_bin_dir)

    collect_ps = rf"{dut_bin_dir}\collect_5min_traces.ps1"
    run_name = scenario.testname  # e.g. perf_stress_050

    interval = Params.get('perf_stress', 'bg_heavy_capture_interval') or '5'
    logging.info(
        f"Starting collect_5min_traces.ps1 in background (instance=perfStressHeavy, "
        f"interval={interval}m, RunName={run_name}). PT numbers will be perturbed "
        f"~10-30% - debug use only."
    )

    scenario._call([
        "cmd.exe",
        f'/C start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File '
        f'"{collect_ps}" -RunName "{run_name}" -IntervalMinutes {interval}',
    ], expected_exit_code="", blocking=False)

    scenario._sleep_to_now()
