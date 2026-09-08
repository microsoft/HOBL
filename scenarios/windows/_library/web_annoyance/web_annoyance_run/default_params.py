# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_annoyance_run', 'load_only', '0', desc='', valOptions=['0', '1'])
    return


def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\web_run')
    import_run_user_only('scenarios\\windows\\_library\\web_annoyance\\web_site_annoyance')
    return