# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('cyberpunk', 'benchmark_loops', '3', desc='Amount of Loops for Benchmarking', valOptions=[])
    Params.setDefault('cyberpunk', 'game_location', 'C:\GOG Games\Cyberpunk 2077', desc='Location of Cyberpunk Game', valOptions=[])
    Params.setDefault('cyberpunk', 'graphics_settings', '', desc='Different Graphics Presets', valOptions=['med_1080', 'rt_ultra_1080', 'rt_low_1440'])
    Params.setDefault('cyberpunk', 'saved_files', '0', desc='', valOptions=['0', '1'])
    Params.setParam(None, 'loop_counter', '2')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\misc\\capture_taskbar')
    return
