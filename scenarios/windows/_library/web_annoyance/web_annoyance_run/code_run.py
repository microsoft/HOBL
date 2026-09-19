# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import json
import os


STOCK_WEB_RUN = 'scenarios\\windows\\_library\\web\\web_run\\web_run.json'
HOOKED_SITES = {
    'web_site_reddit',
    'web_site_instagram',
    'web_site_youtube_tos',
    'web_site_wikipedia',
    'web_site_youtube_nasa',
    'web_site_the_verge',
}
ANNOYANCE_SITE = 'scenarios\\windows\\_library\\web_annoyance\\web_site_annoyance'


def _route_hooked_sites(items):
    for action in items:
        include_path = action.get('include_path', '')
        site_name = include_path.rsplit('\\', 1)[-1]
        if action.get('type') == 'Include' and site_name in HOOKED_SITES:
            action['include_path'] = ANNOYANCE_SITE
            action.setdefault('params', []).append({
                'name': '[site_name]',
                'val_options': '',
                'value': site_name,
            })
        _route_hooked_sites(action.get('children', []))


def build_actions(scenario):
    web_run_path = scenario.resolve(STOCK_WEB_RUN)
    with open(web_run_path, encoding='utf-8') as source:
        actions = json.load(source)
    _route_hooked_sites(actions)
    return scenario._flatten_json(
        actions,
        directory_offset=os.path.dirname(web_run_path),
        component=scenario.component or 'web_annoyance_run',
    )


def run(scenario):
    actions = build_actions(scenario)
    previous_actions = scenario.action_json
    scenario.action_json = actions
    try:
        scenario.run_actions(actions)
    finally:
        scenario.action_json = previous_actions