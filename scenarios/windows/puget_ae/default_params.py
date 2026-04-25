# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('puget_ae', 'benchmark_version', '1.0.0-hobl', desc='Benchmark Version', valOptions=[])
    Params.setDefault('puget_ae', 'puget_license', '', desc='Puget License Key', valOptions=[])
    Params.setDefault('puget_ae', 'loops', '1', desc='Amount of Loops for Test', valOptions=[])
    return

def run_user_only():
    return
