# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    Params.setDefault('mute_unmute', 'probe_name', 'mute_unmute', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'open_taskbar_mode', 'image', desc='', valOptions=['image', 'coordinate', 'keyboard'])
    Params.setDefault('mute_unmute', 'open_taskbar_x', '0', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'open_taskbar_y', '0', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'audio_toggle_mode', 'image', desc='', valOptions=['image', 'coordinate'])
    Params.setDefault('mute_unmute', 'audio_toggle_x', '0', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'audio_toggle_y', '0', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'volume_row_x', '0.770', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'volume_row_y', '0.840', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'volume_row_w', '0.220', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'volume_row_h', '0.095', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'dismiss_action_mode', 'coordinate', desc='', valOptions=['coordinate', 'escape'])
    Params.setDefault('mute_unmute', 'return_x', '0.850', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'return_y', '0.020', desc='', valOptions=[])
    Params.setDefault('mute_unmute', 'dismiss_check_mode', 'image', desc='', valOptions=['image', 'delay'])
    return


def run_user_only():
    return
