# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('teams_verge', 'loops', '4', desc='', valOptions=[])
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam('teams', 'send_screen', '1')
    Params.setParam('teams', 'show_desktop', '1')
    Params.setParam('teams', 'number_of_bots', '1')
    Params.setParam('teams', 'send_video', '1')
    Params.setParam('teams', 'send_audio', '1')
    Params.setParam('teams', 'bots_send_video', '1')
    Params.setParam('teams', 'bots_send_audio', '1')
    Params.setParam('teams', 'bots_share_screen', '0')
    Params.setParam('teams', 'bots_force_subscribe_resolution', '0')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\windows\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_the_verge')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_browser')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    Params.setUserDefault('teams', 'duration', '600', desc='Sets the time in seconds for the test to run.', valOptions=['60', '120', '240', '300', '600', '900'])
    Params.setUserDefault('teams', 'maintain_bots', '0', desc='Set to 1 to have the test periodically check that all bots are present in the call and add bots if needed.', valOptions=['0', '1'])
    return
