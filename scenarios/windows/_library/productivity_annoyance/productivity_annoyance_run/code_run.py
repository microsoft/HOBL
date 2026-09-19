# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import copy
import json
import os

from core.parameters import Params


STOCK_PRODUCTIVITY_IDLE = (
    'scenarios\\windows\\_library\\productivity\\prod_idle\\prod_idle.json'
)

PROBES = {
    'mute_unmute': {
        'include_path': 'scenarios\\windows\\_library\\responsiveness\\mute_unmute',
        'scripted_seconds': 8.5,
    },
    'start_menu_show_apps': {
        'include_path': 'scenarios\\windows\\_library\\responsiveness\\start_menu_show_apps',
        'scripted_seconds': 6.5,
    },
    'explorer_windows_scroll': {
        'include_path': 'scenarios\\windows\\_library\\responsiveness\\explorer_windows_scroll',
        'scripted_seconds': 10.75,
    },
    'explorer_pictures_thumbnails': {
        'include_path': 'scenarios\\windows\\_library\\responsiveness\\explorer_pictures_thumbnails',
        'scripted_seconds': 16.5,
    },
}

IDLE_SLOTS = {
    'V4KHPE': {
        'app': 'outlook',
        'probes': ['mute_unmute', 'start_menu_show_apps'],
    },
    'V4KJ0J': {
        'app': 'excel',
        'probes': ['explorer_windows_scroll'],
    },
    'V4KJ53': {
        'app': 'word',
        'probes': ['explorer_pictures_thumbnails'],
    },
    'V4KJ7E': {
        'app': 'powerpoint',
        'probes': ['mute_unmute', 'start_menu_show_apps'],
    },
    'V4KJ9F': {
        'app': 'onenote',
        'probes': ['explorer_windows_scroll', 'explorer_pictures_thumbnails'],
    },
}

PROBE_GAP_SECONDS = 2.0
VOLUME_ROW_X = '0.770'
VOLUME_ROW_Y = '0.840'
AUDIO_TOGGLE_X = '0.792'
AUDIO_TOGGLE_Y = '0.868'


def _selected_probes():
    value = Params.get('productivity_annoyance', 'probes', log=False) or ''
    return set(value.split())


def _idle_seconds():
    return float(Params.get('productivity_annoyance', 'idle_seconds_per_app', log=False))


def _probe_include(probe_name, app_name, slot_id, index):
    params = [
        {'name': '[probe_name]', 'val_options': '', 'value': probe_name},
        {'name': '[web_phase]', 'val_options': '', 'value': f'productivity_{app_name}'},
        {'name': '[slot_id]', 'val_options': '', 'value': slot_id},
    ]
    if probe_name == 'mute_unmute':
        params.extend([
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[audio_toggle_mode]', 'val_options': '', 'value': 'image'},
            {'name': '[audio_toggle_x]', 'val_options': '', 'value': AUDIO_TOGGLE_X},
            {'name': '[audio_toggle_y]', 'val_options': '', 'value': AUDIO_TOGGLE_Y},
            {'name': '[volume_row_x]', 'val_options': '', 'value': VOLUME_ROW_X},
            {'name': '[volume_row_y]', 'val_options': '', 'value': VOLUME_ROW_Y},
            {'name': '[dismiss_action_mode]', 'val_options': '', 'value': 'escape'},
            {'name': '[dismiss_check_mode]', 'val_options': '', 'value': 'delay'},
        ])
    elif probe_name == 'start_menu_show_apps':
        params.extend([
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[dismiss_mode]', 'val_options': '', 'value': 'escape'},
        ])
    else:
        params.extend([
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[return_focus_mode]', 'val_options': '', 'value': 'none'},
        ])
    return {
        'children': [],
        'delay': '0',
        'description': f'Run {probe_name} in {slot_id}',
        'enabled': True,
        'id': f'PAHOOK{index:03d}',
        'include_path': PROBES[probe_name]['include_path'],
        'params': params,
        'type': 'Include',
    }


def _delay(seconds, description, index):
    return {
        'children': [],
        'delay': f'{seconds:.3f}',
        'description': description,
        'enabled': True,
        'id': f'PAHOOK{index:03d}',
        'type': 'Delay',
    }


def _slot_actions(action, hook_index):
    slot = IDLE_SLOTS[action['id']]
    selected = _selected_probes()
    planned = [name for name in slot['probes'] if name in selected]
    slot_id = f"{slot['app']}_{action['id']}"
    original_seconds = _idle_seconds()
    scripted_seconds = sum(PROBES[name]['scripted_seconds'] for name in planned)
    gap_seconds = PROBE_GAP_SECONDS * max(0, len(planned) - 1)
    residual_seconds = original_seconds - scripted_seconds - gap_seconds
    if residual_seconds < 0:
        raise RuntimeError(
            f'Annoyance plan overruns {slot_id}: '
            f'{scripted_seconds + gap_seconds:.3f}s planned in {original_seconds:.3f}s'
        )

    actions = []
    next_index = hook_index
    for probe_index, probe_name in enumerate(planned):
        actions.append(_probe_include(
            probe_name,
            slot['app'],
            slot_id,
            next_index,
        ))
        next_index += 1
        if probe_index < len(planned) - 1:
            actions.append(_delay(
                PROBE_GAP_SECONDS,
                f'Idle between annoyance probes in {slot_id}',
                next_index,
            ))
            next_index += 1
    actions.append(_delay(
        residual_seconds,
        f'Residual loaded-app idle time for {slot_id}',
        next_index,
    ))
    return actions, next_index + 1


def _replace_slots(items, hook_index=1):
    output = []
    next_index = hook_index
    for original in items:
        action = copy.deepcopy(original)
        if action.get('id') in IDLE_SLOTS:
            replacement, next_index = _slot_actions(action, next_index)
            output.extend(replacement)
            continue
        if action.get('children'):
            action['children'], next_index = _replace_slots(
                action['children'], next_index
            )
        output.append(action)
    return output, next_index


def build_actions(scenario):
    idle_path = scenario.resolve(STOCK_PRODUCTIVITY_IDLE)
    with open(idle_path, encoding='utf-8') as source:
        actions = json.load(source)
    actions, _ = _replace_slots(actions)
    return scenario._flatten_json(
        actions,
        directory_offset=os.path.dirname(idle_path),
        component=scenario.component or 'productivity_annoyance_run',
    )


def run(scenario):
    actions = build_actions(scenario)
    previous_actions = scenario.action_json
    scenario.action_json = actions
    try:
        scenario.run_actions(actions)
    finally:
        scenario.action_json = previous_actions