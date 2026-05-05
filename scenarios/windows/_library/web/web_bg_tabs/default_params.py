# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from functools import partial
import os
from parameters import Params
from utilities.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_bg_tabs', 'bg_tab_loops', '6', desc='Number of iterations of the background-site loop. Each iteration opens 5 tabs (reddit, instagram, wikipedia, youtube_nasa, theverge). Default 6 = 30 bg tabs + 1 apollo foreground = 31 total. perf_stress overrides to 4 (= 20 bg tabs).', valOptions=['1', '2', '3', '4', '5', '6', '8', '10'])
    Params.setParam(None, 'default_typing_delay', '[global:typing_delay]')
    Params.setParam('global', 'typing_delay', '20')
    Params.setParam('global', 'typing_delay', '[default_typing_delay]')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_google_images_apollo')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_instagram')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_reddit')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_the_verge')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_wikipedia')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_youtube_nasa')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    return
