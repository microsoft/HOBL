# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_annoyance_short', 'loops', '1', desc='', valOptions=[])
    Params.setDefault('web_annoyance_short', 'probes', 'mute_unmute start_menu_show_apps explorer_windows_scroll explorer_pictures_thumbnails', desc='Annoyance probes to run.', valOptions=['mute_unmute', 'start_menu_show_apps', 'explorer_windows_scroll', 'explorer_pictures_thumbnails'], multiple=True)
    Params.setDefault('web_annoyance_short', 'machine_profile', 'default', desc='Per-machine calibration profile (Quick-Settings fractions + template set). See _library/responsiveness/machine_profiles.py.', valOptions=['arm64_200', 'xps13', 'default'])
    Params.setDefault('web_annoyance_short', 'power_reporting', '0', desc='Collect whole-run ETW power and 1 Hz per-probe Energy Meter power.', valOptions=['0', '1'])
    if Params.get('web_annoyance_short', 'power_reporting') != '0':
        Params.setParam('global', 'tools', '+power_light annoyance_power')
    Params.setParam(None, 'web_replay_run', '1')
    Params.setParam(None, 'phase_reporting', '1')
    return


def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\web\\web_check')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_kill')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_setup')
    import_run_user_only('scenarios\\windows\\_library\\web_annoyance\\web_site_wikipedia_annoyance')
    return