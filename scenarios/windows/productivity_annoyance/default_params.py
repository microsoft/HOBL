# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault(
        'productivity_annoyance',
        'probes',
        'mute_unmute start_menu_show_apps explorer_windows_scroll explorer_pictures_thumbnails',
        desc='Annoyance probes to run.',
        valOptions=[
            'mute_unmute',
            'start_menu_show_apps',
            'explorer_windows_scroll',
            'explorer_pictures_thumbnails',
        ],
        multiple=True,
    )
    Params.setDefault(
        'productivity_annoyance',
        'machine_profile',
        'default',
        desc='Per-machine calibration profile (Quick-Settings fractions + template set). See _library/responsiveness/machine_profiles.py.',
        valOptions=['arm64_200', 'xps13', 'default'],
    )
    Params.setDefault(
        'productivity_annoyance',
        'power_reporting',
        '1',
        desc='Collect ETW power plus aligned 1 Hz Energy Meter and memory telemetry.',
        valOptions=['0', '1'],
    )
    Params.setDefault(
        'productivity_annoyance',
        'idle_seconds_per_app',
        '111',
        desc='Loaded-app idle duration for each Office application.',
        valOptions=[],
    )
    if Params.get('productivity_annoyance', 'power_reporting') != '0':
        Params.setParam('global', 'tools', '+power_light annoyance_power')
    Params.setParam(None, 'phase_reporting', '1')
    return


def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_kill')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_setup')
    import_run_user_only('scenarios\\windows\\_library\\productivity_annoyance\\productivity_annoyance_run')
    return