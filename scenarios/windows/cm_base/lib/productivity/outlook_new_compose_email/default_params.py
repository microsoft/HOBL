# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('outlook_new_compose_email', 'short_typing', '0', desc='Use the shortened email body when enabled', valOptions=['0', '1'])
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_begin')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_end')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_new_open')
    import_run_user_only('scenarios\\windows\\cm_base\\lib\\productivity\\outlook_new_open_compose')
    import_run_user_only('scenarios\\windows\\cm_base\\lib\\productivity\\outlook_new_discard_email')
    return
