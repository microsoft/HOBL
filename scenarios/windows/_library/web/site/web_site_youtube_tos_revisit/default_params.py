# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_site_youtube_tos_revisit', 'revisit_tag', '', desc='', valOptions=[])
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\web_resume_video')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_tab_switch')
    return
