# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('cm_base', 'background_teams', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('cm_base', 'background_onedrive_copy', '1', desc='', valOptions=['0', '1'])
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam(None, 'phase_reporting', '1')
    Params.setDefault('cm_base', 'perf_run', '0', desc='', valOptions=['0', '1'])
    Params.setParam('teams', 'collect_MSTeams_Logs', '0')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\perf_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\perf_teardown')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_kill')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_setup')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_tabs')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_run_minwin')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    Params.setUserDefault(None, 'minwin_workloads', '', desc='', valOptions=['live_captions', 'copilot_query', 'semantic_search', 'click_todo', 'studioeffect_blur', 'productivity', 'snipping_tool', 'file_explorer'], multiple=True)
    return
