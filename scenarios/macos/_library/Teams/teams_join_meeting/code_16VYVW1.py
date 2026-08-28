# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params
import time


def run(scenario):
    logging.debug('Executing code block: code_16VYVW1.py')
    join_meeting_uri = Params.get('teams', 'join_meeting_uri')
    
    scenario._call(["open", f"{join_meeting_uri}"])
    time.sleep(5)
    scenario._call(["open", f"{join_meeting_uri}"])