# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('mincp_base', 'background_timers', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('mincp_base', 'background_teams', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('mincp_base', 'background_onedrive_copy', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('mincp_base', 'simple_office_launch', '0', desc='', valOptions=['1', '0'])
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam(None, 'phase_reporting', '1')
    Params.setDefault('mincp_base', 'perf_run', '0', desc='', valOptions=['0', '1'])
    # DO NOT REMOVE these 3 lines - they are required for mincp_base to run correctly
    Params.setDefault('web_enter_address', 'web_site_load_time', '20', desc='', valOptions=[])
    Params.setOverride('global', 'short_typing', '1')
    Params.setDefault('mincp_base', 'web_workload', 'reddit', desc='Specific websites to run during mincp workload. reddit must be included (Tab 1 with new_tab=0).', valOptions=['amazonbsg', 'amazongot', 'amazonvacuum', 'googleimagesapollo', 'googleimageslondon', 'googlesearchbelgium', 'googlesearchsuperbowl', 'instagram', 'reddit', 'theverge', 'wikipedia', 'youtubenasa', 'youtubetos'], multiple=True)
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\live_captions_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\perf_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\perf_teardown')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\semantic_search_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\semantic_search_teardown')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\timers_setup')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\timers_teardown')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_file_explorer')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_to_do_setup')
    import_run_user_only('scenarios\\windows\\_library\\misc\\click_to_do_teardown')
    import_run_user_only('scenarios\\windows\\_library\\misc\\etw_event_tag')
    import_run_user_only('scenarios\\windows\\_library\\misc\\perf_click_to_do')
    import_run_user_only('scenarios\\windows\\_library\\misc\\search_taskbar')
    import_run_user_only('scenarios\\windows\\_library\\misc\\start_app_launch')
    import_run_user_only('scenarios\\windows\\_library\\misc\\studio_effect_blur')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_kill')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_setup')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_switchto')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_tabs')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_run_mincp')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_switchto')
    Params.setUserDefault(None, 'mincp_workloads', '', desc='', valOptions=['live_captions', 'copilot_query', 'semantic_search', 'click_todo', 'studioeffect_blur', 'productivity', 'file_explorer', 'start_launch'], multiple=True)
    return
