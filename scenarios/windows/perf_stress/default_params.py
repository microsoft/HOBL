# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('perf_stress', 'background_teams', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'stress_run', '1', desc='For perf metrics', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'stress_cpu_target', '65', desc='Target CPU load percentage for stress mode.', valOptions=['0', '25', '50', '65', '75', '85'])
    Params.setDefault('perf_stress', 'web_workload', 'reddit amazongot googleimagesapollo youtubetos', desc='Specific websites to run during stress workload. reddit must be included (Tab 1 with new_tab=0).', valOptions=['amazonbsg', 'amazongot', 'amazonvacuum', 'googleimagesapollo', 'googleimageslondon', 'googlesearchbelgium', 'googlesearchsuperbowl', 'instagram', 'reddit', 'theverge', 'wikipedia', 'youtubenasa', 'youtubetos'])
    Params.setDefault('perf_stress', 'background_onedrive_copy', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'simple_office_launch', '1', desc='', valOptions=['1', '0'])
    Params.setDefault('perf_stress', 'shell_probes', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'sleep_resume_midrun', '0', desc='This will actually sleep the DUT (pressing the power button)', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'edge_close_relaunch', '0', desc='1 = mid-run kill msedge and relaunch with 12 foreground sites. Side effect: destroys background Edge tabs (no automatic restore). Default 0 keeps bg tabs alive for the entire run.', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'perftrack_app_launch', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'provider', 'perf_utc.wprp', desc='WPRP file to use for perf_utc tracing.', valOptions=['@\\providers'])
    Params.setDefault('perf_stress', 'bg_heavy_capture', '0', desc='1 = launch collect_5min_traces.ps1 in the background on the DUT alongside the core perf_utc trace. Uses a named WPR instance (perfStressHeavy). Saves rolling ETLs to C:\WPR_Traces\<runname>\WPR_<timestamp>.etl. WARNING: dual-session WPR perturbs PT numbers ~10-30%% - debug use only.', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'bg_heavy_capture_interval', '5', desc='Rolling ETL segment length in minutes for bg_heavy_capture (default 5).', valOptions=['2', '3', '4', '5'])
    Params.setDefault('perf_stress', 'bg_edge_tabs', '1', desc='1 = open background Edge tabs to increase memory pressure and CPU stress.', valOptions=['0', '1'])
    Params.setDefault('perf_stress', 'bg_edge_tab_loops', '6', desc='Iterations of the web_bg_tabs site loop. Each iteration opens 5 background Edge tabs. Default 6 = 30 background tabs', valOptions=['1', '2', '3', '4', '5', '6', '8', '10'])
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam(None, 'phase_reporting', '1')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_file_explorer')
    import_run_user_only('scenarios\\windows\\_library\\misc\\etw_event_tag')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_begin')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_end')
    import_run_user_only('scenarios\\windows\\_library\\misc\\start_app_launch')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_kill')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_setup')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_run')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_bg_tabs')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_tabs')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_run_12')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_switchto')
    return
