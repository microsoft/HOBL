# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Per-machine calibration profiles for the responsiveness annoyance probes.

The probes locate UI with DPI-tagged image templates, so they are scale-portable.
A handful of Quick-Settings capture-region / cursor-park / coordinate-fallback
fractions still depend on the target machine's QS layout, display scale, and theme.
Those live here, keyed by a profile name chosen with the ``machine_profile`` param,
so onboarding a new DUT means adding one profile entry (and recapturing templates)
instead of editing scenario schedules.
"""
import logging

from core.parameters import Params

# Mute-probe calibration keys a profile may set on the 'mute_unmute' section.
CAL_KEYS = ('audio_toggle_mode', 'audio_toggle_x', 'audio_toggle_y',
            'volume_row_x', 'volume_row_y', 'volume_row_w', 'volume_row_h',
            'return_x', 'return_y')

PROFILES = {
    # ARM64 reference, 3270x2180 @ 200%, dark theme.
    'arm64_200': {
        'audio_toggle_mode': 'image',
        'audio_toggle_x': '0.792', 'audio_toggle_y': '0.868',
        'volume_row_x': '0.770', 'volume_row_y': '0.840',
        'volume_row_w': '0.220', 'volume_row_h': '0.095',
        'return_x': '0.850', 'return_y': '0.020',
    },
    # x64 reference (Dell XPS 13), 2560x1600 @ 200%, dark theme. Same 200% scale as the ARM64
    # profile, so the DPI-192 templates are reused; only the QS fractions differ. The volume-row capture
    # width is wider (0.300) because the fixed-pixel QS row is a larger fraction of the narrower
    # 2560-wide panel. Mute toggle validated on-device.
    'xps13': {
        'audio_toggle_mode': 'image',
        'audio_toggle_x': '0', 'audio_toggle_y': '0',
        'volume_row_x': '0.700', 'volume_row_y': '0.790',
        'volume_row_w': '0.300', 'volume_row_h': '0.095',
        'return_x': '0.850', 'return_y': '0.020',
    },
    # Neutral starting point for a new machine: image mode, no coordinate fallback.
    # Recalibrate volume_row_* to bound the QS volume row, recapture templates, then
    # copy into a named profile for that DUT.
    'default': {
        'audio_toggle_mode': 'image',
        'audio_toggle_x': '0', 'audio_toggle_y': '0',
        'volume_row_x': '0.770', 'volume_row_y': '0.840',
        'volume_row_w': '0.220', 'volume_row_h': '0.095',
        'return_x': '0.850', 'return_y': '0.020',
    },
}

DEFAULT_PROFILE = 'default'


def get_profile(name):
    """Return the calibration dict for ``name``, falling back to 'default'."""
    prof = PROFILES.get((name or '').strip())
    if prof is None:
        logging.warning("machine_profiles: unknown profile '%s'; using 'default'. Known: %s",
                        name, ', '.join(sorted(PROFILES)))
        prof = PROFILES['default']
    return prof


def resolve_name(section):
    """Read the selected ``machine_profile`` for a scenario section (or the default)."""
    return (Params.get(section, 'machine_profile', log=False) or DEFAULT_PROFILE).strip()


def apply_to_mute(section):
    """Override the mute_unmute calibration params from the section's selected profile.

    Lets web/productivity annoyance (which run the probe from a static schedule and
    otherwise inherit the library defaults) pick up per-machine values.
    """
    prof = get_profile(resolve_name(section))
    for key in CAL_KEYS:
        if key in prof:
            Params.setOverride('mute_unmute', key, prof[key])
