# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('idle_annoyance', 'schedule', 'paired_web', desc='Baseline schedule to run.', valOptions=['paired_web'])
    Params.setDefault('idle_annoyance', 'cycles', '1', desc='Number of complete paired schedules to run.', valOptions=[])
    Params.setDefault('idle_annoyance', 'probes', 'mute_unmute start_menu_show_apps explorer_windows_scroll explorer_pictures_thumbnails', desc='Annoyance probes to run.', valOptions=['mute_unmute', 'start_menu_show_apps', 'explorer_windows_scroll', 'explorer_pictures_thumbnails'], multiple=True)
    Params.setDefault('idle_annoyance', 'machine_profile', 'default', desc='Per-machine calibration profile (Quick-Settings fractions + template set). See _library/responsiveness/machine_profiles.py.', valOptions=['arm64_200', 'xps13', 'default'])
    Params.setDefault('idle_annoyance', 'desktop_settle_seconds', '5', desc='Seconds to settle after minimizing to the connected desktop.', valOptions=[])
    Params.setDefault('idle_annoyance', 'power_reporting', '1', desc='Collect ETW power plus aligned 1 Hz Energy Meter and memory telemetry.', valOptions=['0', '1'])
    if Params.get('idle_annoyance', 'power_reporting') != '0':
        Params.setParam('global', 'tools', '+power_light annoyance_power')
    Params.setParam(None, 'phase_reporting', '1')
    return


def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_begin')
    import_run_user_only('scenarios\\windows\\_library\\misc\\recording_phase_end')
    import_run_user_only('scenarios\\windows\\_library\\responsiveness\\explorer_pictures_thumbnails')
    import_run_user_only('scenarios\\windows\\_library\\responsiveness\\explorer_windows_scroll')
    import_run_user_only('scenarios\\windows\\_library\\responsiveness\\mute_unmute')
    import_run_user_only('scenarios\\windows\\_library\\responsiveness\\start_menu_show_apps')
    return