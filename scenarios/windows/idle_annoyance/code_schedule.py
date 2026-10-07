# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os

from core.parameters import Params
from scenarios.windows._library.responsiveness import machine_profiles


CYCLE_DURATION_SECONDS = 1124.0

PROBES = {
    'mute_unmute': 'scenarios\\windows\\_library\\responsiveness\\mute_unmute',
    'start_menu_show_apps': 'scenarios\\windows\\_library\\responsiveness\\start_menu_show_apps',
    'explorer_windows_scroll': 'scenarios\\windows\\_library\\responsiveness\\explorer_windows_scroll',
    'explorer_pictures_thumbnails': 'scenarios\\windows\\_library\\responsiveness\\explorer_pictures_thumbnails',
}

PAIRED_WEB_SCHEDULE = [
    (39.00, 'mute_unmute', 'reddit_UC69K4'),
    (49.50, 'start_menu_show_apps', 'reddit_UC69K4'),
    (58.00, 'explorer_windows_scroll', 'reddit_UC69K4'),
    (191.30, 'mute_unmute', 'instagram_UCJ082'),
    (201.80, 'start_menu_show_apps', 'instagram_UCJ082'),
    (221.50, 'mute_unmute', 'instagram_UCHYN5'),
    (232.00, 'explorer_windows_scroll', 'instagram_UCHYN5'),
    (595.50, 'start_menu_show_apps', 'youtube_tos_UCL4U1'),
    (604.00, 'explorer_windows_scroll', 'youtube_tos_UCL4U1'),
    (618.05, 'explorer_pictures_thumbnails', 'youtube_tos_UCL4U1'),
    (715.85, 'start_menu_show_apps', 'wikipedia_UC6L36'),
    (761.75, 'mute_unmute', 'youtube_nasa_UCL4U1'),
    (772.25, 'start_menu_show_apps', 'youtube_nasa_UCL4U1'),
    (780.75, 'explorer_windows_scroll', 'youtube_nasa_UCL4U1'),
    (794.80, 'explorer_pictures_thumbnails', 'youtube_nasa_UCL4U1'),
    (1005.70, 'start_menu_show_apps', 'the_verge_UC6L36'),
    (1014.20, 'explorer_pictures_thumbnails', 'the_verge_UC6L36'),
]


def _delay_to(seconds, index):
    return {
        'children': [],
        'delay': f'{seconds:.3f}',
        'description': f'Wait for paired baseline time {seconds:.3f}s',
        'enabled': True,
        'id': f'IASCHED{index:03d}',
        'type': 'Delay To',
    }


def _probe_include(probe_name, slot_id, cycle, index, cal):
    params = [
        {'name': '[probe_name]', 'val_options': '', 'value': probe_name},
        {'name': '[web_phase]', 'val_options': '', 'value': 'idle_desktop'},
        {'name': '[slot_id]', 'val_options': '', 'value': slot_id},
    ]
    if probe_name == 'mute_unmute':
        params.extend([
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[audio_toggle_mode]', 'val_options': '', 'value': cal['audio_toggle_mode']},
            {'name': '[audio_toggle_x]', 'val_options': '', 'value': cal['audio_toggle_x']},
            {'name': '[audio_toggle_y]', 'val_options': '', 'value': cal['audio_toggle_y']},
            {'name': '[volume_row_x]', 'val_options': '', 'value': cal['volume_row_x']},
            {'name': '[volume_row_y]', 'val_options': '', 'value': cal['volume_row_y']},
            {'name': '[volume_row_w]', 'val_options': '', 'value': cal['volume_row_w']},
            {'name': '[volume_row_h]', 'val_options': '', 'value': cal['volume_row_h']},
            {'name': '[dismiss_action_mode]', 'val_options': '', 'value': 'escape'},
            {'name': '[dismiss_check_mode]', 'val_options': '', 'value': 'delay'},
            {'name': '[return_x]', 'val_options': '', 'value': cal['return_x']},
            {'name': '[return_y]', 'val_options': '', 'value': cal['return_y']},
        ])
    elif probe_name == 'start_menu_show_apps':
        params.extend([
            {'name': '[return_x]', 'val_options': '', 'value': cal['return_x']},
            {'name': '[return_y]', 'val_options': '', 'value': cal['return_y']},
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[dismiss_mode]', 'val_options': '', 'value': 'escape'},
        ])
    else:
        params.extend([
            {'name': '[return_x]', 'val_options': '', 'value': cal['return_x']},
            {'name': '[return_y]', 'val_options': '', 'value': cal['return_y']},
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[return_focus_mode]', 'val_options': '', 'value': 'coordinate'},
        ])
    return {
        'children': [],
        'delay': '0',
        'description': f'Run idle paired {probe_name} for {slot_id}, cycle {cycle}',
        'enabled': True,
        'id': f'IAPROBE{index:03d}',
        'include_path': PROBES[probe_name],
        'params': params,
        'type': 'Include',
    }


def build_actions(scenario):
    schedule = Params.get('idle_annoyance', 'schedule', log=False)
    if schedule != 'paired_web':
        raise ValueError(f'Unsupported idle annoyance schedule: {schedule}')
    selected = set((Params.get('idle_annoyance', 'probes', log=False) or '').split())
    unknown = selected.difference(PROBES)
    if unknown:
        raise ValueError(f'Unsupported idle annoyance probes: {sorted(unknown)}')
    cycles = int(Params.get('idle_annoyance', 'cycles', log=False))
    if cycles < 1:
        raise ValueError('idle_annoyance:cycles must be at least 1')

    cal = machine_profiles.get_profile(machine_profiles.resolve_name('idle_annoyance'))

    actions = []
    action_index = 1
    for cycle in range(1, cycles + 1):
        cycle_offset = (cycle - 1) * CYCLE_DURATION_SECONDS
        for start_seconds, probe_name, slot_id in PAIRED_WEB_SCHEDULE:
            if probe_name not in selected:
                continue
            actions.append(_delay_to(cycle_offset + start_seconds, action_index))
            action_index += 1
            actions.append(_probe_include(probe_name, slot_id, cycle, action_index, cal))
            action_index += 1
        actions.append(_delay_to(cycle * CYCLE_DURATION_SECONDS, action_index))
        action_index += 1

    return scenario._flatten_json(
        actions,
        directory_offset=os.path.dirname(__file__),
        component='idle_annoyance',
    )


def run(scenario):
    actions = build_actions(scenario)
    previous_actions = scenario.action_json
    scenario.action_json = actions
    try:
        scenario.run_actions(actions)
    finally:
        scenario.action_json = previous_actions