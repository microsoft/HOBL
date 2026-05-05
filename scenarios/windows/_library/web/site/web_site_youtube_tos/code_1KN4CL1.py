# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1KN4CL1.py')
    enable = Params.get("web", "youtube_screenshot")
    if enable == "1":
        index = Params.get("youtube_tos", "screenshot_index")
        if index == None or "":
            index = 0
        index = int(index)
        scenario._screenshot(f"youtube_tos_{index:03}.png")
        Params.setParam("youtube_tos", "screenshot_index", str(index+1))