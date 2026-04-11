# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_site_youtube_tos', 'new_tab', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('web_site_youtube_tos', 'load_only', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('web_site_youtube_tos', 'enable_pause', '1', desc='', valOptions=['0', '1'])
    Params.setDefault('web_site_youtube_tos', 'full_screen', '0', desc='', valOptions=['0', '1'])
    Params.setDefault('web_site_youtube_tos', 'duration', '120', desc='Video playback duration', valOptions=[])
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_begin')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_end')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_enter_address')
    return
