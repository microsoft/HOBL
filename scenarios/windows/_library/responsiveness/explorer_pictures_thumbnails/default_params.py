# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""explorer_pictures_thumbnails probe parameters.

PROVISIONAL / work-in-progress metric. The current endpoint (first_thumbnail_visible) can
match a generic placeholder tile before the real thumbnails render, so under memory pressure
it may under-report the true thumbnail-view latency. The probe is shipped and runnable, but
its latency is not yet a validated metric. Planned improvement: an N-of-N fully-rendered
detector that discriminates real thumbnails from placeholders (see the annoyance PR notes).
"""

from core.parameters import Params


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    Params.setDefault('explorer_pictures_thumbnails', 'probe_name', 'explorer_pictures_thumbnails', desc='', valOptions=[])
    Params.setDefault('explorer_pictures_thumbnails', 'return_x', '0.850', desc='', valOptions=[])
    Params.setDefault('explorer_pictures_thumbnails', 'return_y', '0.020', desc='', valOptions=[])
    Params.setDefault('explorer_pictures_thumbnails', 'open_taskbar_mode', 'image', desc='', valOptions=['image', 'coordinate', 'keyboard'])
    Params.setDefault('explorer_pictures_thumbnails', 'open_taskbar_x', '0', desc='', valOptions=[])
    Params.setDefault('explorer_pictures_thumbnails', 'open_taskbar_y', '0', desc='', valOptions=[])
    Params.setDefault('explorer_pictures_thumbnails', 'return_focus_mode', 'coordinate', desc='', valOptions=['coordinate', 'none'])
    Params.setDefault('explorer_pictures_thumbnails', 'fixture_count', '24', desc='Number of deterministic Pictures files used for thumbnail readiness.', valOptions=[])
    return


def run_user_only():
    return
