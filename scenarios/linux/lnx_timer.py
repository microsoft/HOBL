# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from builtins import *
import logging
import core.app_scenario
import time
from core.parameters import Params

# Just a simple test case for testing out infrastructure
# For collecting data and running tools, use the manual.py scenario

class LnxTimer(core.app_scenario.Scenario):
    logging.info("In LnxTimer")
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'duration', '1')  # Seconds

    def runTest(self):
        self.duration = Params.get(self.module, 'duration')
        logging.info("Delaying for " + self.duration + " seconds")
        time.sleep(float(self.duration))
    