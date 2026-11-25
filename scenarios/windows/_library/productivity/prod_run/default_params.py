# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_onenote_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_onenote_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_new_manarola')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_new_review')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_new_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_switchto')
    return
