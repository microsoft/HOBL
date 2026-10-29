# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from functools import partial
import os
from core.parameters import Params
import utilities.open_source.modules

import_run_user_only = partial(utilities.open_source.modules.import_run_user_only, here=__file__)

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('idle_apps_min', 'duration', '900', desc='Idle time in seconds with all apps minimized. Default is 900 seconds.', valOptions=[])
    Params.setParam(None, 'web_replay_run', '1')
    return

def run_user_only():
    import_run_user_only('..\\_library\\web\\web_switchto')
    import_run_user_only('..\\_library\\web\\web_close_tabs')
    import_run_user_only('..\\_library\\productivity\\prod_kill')
    import_run_user_only('..\\_library\\productivity\\prod_close')
    import_run_user_only('..\\_library\\productivity\\prod_setup')
    import_run_user_only('..\\_library\\web\\web_setup')
    import_run_user_only('..\\_library\\web\\web_close_browser')
    import_run_user_only('..\\_library\\web\\web_run')
    import_run_user_only('..\\_library\\productivity\\prod_open')
    import_run_user_only('..\\_library\\web\\web_kill')
    return
