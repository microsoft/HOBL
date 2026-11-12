# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    Params.setDefault('explorer_windows_scroll', 'probe_name', 'explorer_windows_scroll', desc='', valOptions=[])
    Params.setDefault('explorer_windows_scroll', 'return_x', '0.850', desc='', valOptions=[])
    Params.setDefault('explorer_windows_scroll', 'return_y', '0.020', desc='', valOptions=[])
    Params.setDefault('explorer_windows_scroll', 'open_taskbar_mode', 'image', desc='', valOptions=['image', 'coordinate', 'keyboard'])
    Params.setDefault('explorer_windows_scroll', 'open_taskbar_x', '0', desc='', valOptions=[])
    Params.setDefault('explorer_windows_scroll', 'open_taskbar_y', '0', desc='', valOptions=[])
    Params.setDefault('explorer_windows_scroll', 'return_focus_mode', 'coordinate', desc='', valOptions=['coordinate', 'none'])
    return


def run_user_only():
    return
