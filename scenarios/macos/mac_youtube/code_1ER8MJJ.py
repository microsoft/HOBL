# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import math
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1ER8MJJ.py')

    duration      = int(Params.get("mac_youtube", "duration"))
    loop_duration = int(Params.get("mac_youtube", "loop_duration"))

    loops = math.ceil(duration / loop_duration)
    logging.info(f"Looping set for {loops} iteration{'s' if loops != 1 else ''}")
    Params.setParam("mac_youtube", "loops", str(loops))
