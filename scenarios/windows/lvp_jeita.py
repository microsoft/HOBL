# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Invoke lvp scenario with video_file set to JB2_0.mp4
##

from core.parameters import Params
Params.setOverride("lvp_jeita", "title", "JB3_0-MOVIE")
Params.setOverride("lvp_jeita", "airplane_mode", "0")
import scenarios.windows.lvp

Params.setAssociatedSections("lvp_jeita", ["lvp"])

class LvpJeitaPrep(scenarios.windows.lvp.LVP):
    """
    Plays a video in full screen mode in accordance with requirements set by the Japan Electronics and Information Technology Industries Association for battery operated electronic devices being released in Japan.

    Please do not alter parameters as they have been set to meet the requirements of that governing body
    """
    module = __module__.split('.')[-1]

