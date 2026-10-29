# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('netflix', 'duration', '600', desc='', valOptions=[])
    Params.setDefault('netflix', 'netflix_username', '', desc='', valOptions=[])
    Params.setDefault('netflix', 'netflix_password', '', desc='', valOptions=[])
    Params.setDefault('netflix', 'enable_info_collection', '1', desc='', valOptions=['0', '1'])
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_close_browser')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_enter_address')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    return
