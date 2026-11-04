# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('youtube', 'duration', '600', desc='Total scenario duration', valOptions=[])
    Params.setDefault('youtube', 'loop_duration', '300', desc='YouTube video playback duration before looping (max 480s)', valOptions=[])
    Params.setDefault('youtube', 'full_screen', '0', desc='Full Screen mode', valOptions=['0', '1'])
    Params.setParam(None, 'web_replay_run', '1')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_youtube_tos')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_browser')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    return
