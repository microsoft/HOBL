# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('enterprise_collab', 'background_timers', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'background_teams', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'background_onedrive_copy', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'simple_office_launch', '0', desc='', valOptions=['1', '0'])
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam(None, 'phase_reporting', '1')
    Params.setDefault('enterprise_collab', 'perf_run', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'file_explorer', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'snipping_tool', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('enterprise_collab', 'settings_app', '0', desc='', valOptions=['0', '1'])
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\diagnostics_disable')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\diagnostics_enable')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\timers_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\timers_teardown')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_file_explorer')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_settings')
    import_run_user_only('scenarios\\windows\\_library\\misc\\etw_event_tag')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_begin')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_end')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_kill')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_setup')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_tabs')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_run_12')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_switchto')
    return
