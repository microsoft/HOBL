# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import copy
import json
import os

from core.parameters import Params


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

SITE_HOOKS = {
    'web_site_reddit': {
        'UC69K4': ['mute_unmute', 'start_menu_show_apps', 'explorer_windows_scroll'],
    },
    'web_site_instagram': {
        'UCJ082': ['mute_unmute', 'start_menu_show_apps'],
        'UCHYN5': ['mute_unmute', 'explorer_windows_scroll'],
    },
    'web_site_youtube_tos': {
        'UCL4U1': ['start_menu_show_apps', 'explorer_windows_scroll', 'explorer_pictures_thumbnails'],
    },
    'web_site_wikipedia': {
        'UC6L36': ['start_menu_show_apps'],
    },
    'web_site_youtube_nasa': {
        'UCL4U1': [
            'mute_unmute',
            'start_menu_show_apps',
            'explorer_windows_scroll',
            'explorer_pictures_thumbnails',
        ],
    },
    'web_site_the_verge': {
        'UC6L36': ['start_menu_show_apps', 'explorer_pictures_thumbnails'],
    },
}

SITE_DELAY_ADJUSTMENTS = {
    ('web_site_youtube_tos', 'UCL4U1'): -44.0,
}

CAPTURE_OVERRIDES = {
    ('web_site_instagram', 'UCHFX3'): {
        'h': '0.600',
        'y': '0.400',
    },
}

PROBE_GAP_SECONDS = 2.0
RETURN_X = '0.850'
RETURN_Y = '0.020'
VOLUME_ROW_X = '0.770'
VOLUME_ROW_Y = '0.840'
AUDIO_TOGGLE_X = '0.792'
AUDIO_TOGGLE_Y = '0.868'


def _site_path(site_name):
    return (
        'scenarios\\windows\\_library\\web\\site\\'
        f'{site_name}\\{site_name}.json'
    )


def _selected_probes():
    value = Params.get('web_annoyance', 'probes', log=False) or ''
    return set(value.split())


def _probe_include(probe_name, site_name, slot_id, index):
    params = [
        {'name': '[probe_name]', 'val_options': '', 'value': probe_name},
        {'name': '[web_phase]', 'val_options': '', 'value': site_name.removeprefix('web_site_')},
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
            {'name': '[return_x]', 'val_options': '', 'value': RETURN_X},
            {'name': '[return_y]', 'val_options': '', 'value': RETURN_Y},
        ])
    elif probe_name == 'start_menu_show_apps':
        params.extend([
            {'name': '[return_x]', 'val_options': '', 'value': RETURN_X},
            {'name': '[return_y]', 'val_options': '', 'value': RETURN_Y},
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[dismiss_mode]', 'val_options': '', 'value': 'escape'},
        ])
    else:
        params.extend([
            {'name': '[return_x]', 'val_options': '', 'value': RETURN_X},
            {'name': '[return_y]', 'val_options': '', 'value': RETURN_Y},
            {'name': '[open_taskbar_mode]', 'val_options': '', 'value': 'keyboard'},
            {'name': '[return_focus_mode]', 'val_options': '', 'value': 'coordinate'},
        ])
    return {
        'children': [],
        'delay': '0',
        'description': f'Run {probe_name} in {slot_id}',
        'enabled': True,
        'id': f'WAHOOK{index:03d}',
        'include_path': PROBES[probe_name]['include_path'],
        'params': params,
        'type': 'Include',
    }


def _slot_actions(scenario, component, site_name, action, hook_index):
    selected = _selected_probes()
    planned = [name for name in SITE_HOOKS[site_name][action['id']] if name in selected]
    original_seconds = float(scenario._resolve_params_in_item(action['delay'], component))
    original_seconds += SITE_DELAY_ADJUSTMENTS.get((site_name, action['id']), 0.0)
    slot_id = f"{site_name.removeprefix('web_site_')}_{action['id']}"
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
        actions.append(_probe_include(probe_name, site_name, slot_id, next_index))
        next_index += 1
        if probe_index < len(planned) - 1:
            actions.append({
                'children': [],
                'delay': f'{PROBE_GAP_SECONDS:.3f}',
                'description': f'Idle between annoyance probes in {slot_id}',
                'enabled': True,
                'id': f'WAHOOK{next_index:03d}',
                'type': 'Delay',
            })
            next_index += 1
    actions.append({
        'children': [],
        'delay': f'{residual_seconds:.3f}',
        'description': f'Residual stock idle time for {slot_id}',
        'enabled': True,
        'id': f'WAHOOK{next_index:03d}',
        'type': 'Delay',
    })
    return actions, next_index + 1


def _replace_hooks(scenario, component, site_name, items, hook_index=1):
    output = []
    hooks = SITE_HOOKS[site_name]
    next_index = hook_index
    for original in items:
        action = copy.deepcopy(original)
        action.update(CAPTURE_OVERRIDES.get((site_name, action.get('id')), {}))
        if action.get('id') in hooks:
            replacement, next_index = _slot_actions(
                scenario, component, site_name, action, next_index
            )
            output.extend(replacement)
            continue
        if action.get('children'):
            action['children'], next_index = _replace_hooks(
                scenario, component, site_name, action['children'], next_index
            )
        output.append(action)
    return output, next_index


def build_actions(scenario):
    component = scenario.component or 'web_site_annoyance'
    site_name = Params.get(component, 'site_name', log=False)
    if site_name not in SITE_HOOKS:
        raise ValueError(f'Unsupported annoyance site: {site_name}')
    site_path = scenario.resolve(_site_path(site_name))
    with open(site_path, encoding='utf-8') as source:
        stock_actions = json.load(source)
    hooked_actions, _ = _replace_hooks(
        scenario, component, site_name, stock_actions
    )
    return scenario._flatten_json(
        hooked_actions,
        directory_offset=os.path.dirname(site_path),
        component=component,
    )


def run(scenario):
    actions = build_actions(scenario)
    previous_actions = scenario.action_json
    scenario.action_json = actions
    try:
        scenario.run_actions(actions)
    finally:
        scenario.action_json = previous_actions