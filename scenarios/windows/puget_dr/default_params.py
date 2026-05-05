# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('puget_dr', 'benchmark_version', '2.0.1', desc='Benchmark Version', valOptions=[])
    Params.setDefault('puget_dr', 'puget_license', '', desc='Puget License Key', valOptions=[])
    Params.setDefault('puget_dr', 'loops', '1', desc='Amount of Loops for Test', valOptions=[])
    return

def run_user_only():
    return
