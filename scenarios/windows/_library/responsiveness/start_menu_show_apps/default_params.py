# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    Params.setDefault('start_menu_show_apps', 'probe_name', 'start_menu_show_apps', desc='', valOptions=[])
    Params.setDefault('start_menu_show_apps', 'return_x', '0.850', desc='', valOptions=[])
    Params.setDefault('start_menu_show_apps', 'return_y', '0.020', desc='', valOptions=[])
    Params.setDefault('start_menu_show_apps', 'open_taskbar_mode', 'image', desc='', valOptions=['image', 'coordinate', 'keyboard'])
    Params.setDefault('start_menu_show_apps', 'open_taskbar_x', '0', desc='', valOptions=[])
    Params.setDefault('start_menu_show_apps', 'open_taskbar_y', '0', desc='', valOptions=[])
    Params.setDefault('start_menu_show_apps', 'dismiss_mode', 'coordinate', desc='', valOptions=['coordinate', 'escape'])
    return


def run_user_only():
    return
