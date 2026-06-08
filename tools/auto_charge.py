# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Disengage charger at beginning of scenario and re-engage when complete

# 4 specified functions
# Can't block duration of test
# Parameters specified in callback, like result_dir, scenario name?

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import time

class Tool(Scenario):
    '''
    Turn off/on charger before scenario, turn on charger after.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'delay', '5')
    Params.setDefault(module, 'mode', 'DC') # DC or AC
    conn_timeout = False

    # Get parameters
    charge_on_call = Params.get('global', 'charge_on_call')
    charge_off_call = Params.get('global', 'charge_off_call')

    delay = Params.get(module, 'delay')
    mode = Params.get(module, 'mode')

    def initCallback(self, scenario):
        self.conn_timeout = False
        if self.mode == "AC":
            # Engage charging
            logging.info("Attempting to turn on charger...")
            if self.charge_on_call != "" and self.charge_on_call != None:
                self._host_call(self.charge_on_call)
                logging.info("Charger turned on.")
            else:
                logging.warning("No charge_on_call specified.")
            if Params.get('global', 'local_execution') == '1':
                self._host_call('utilities\\MsgPrompt.exe -WaitForAC')
                logging.info("Charger plugged in.")
        else:
            # Disengage charging
            logging.info("Attempting to turn off charger...")
            if self.charge_off_call != "" and self.charge_off_call != None:
                self._host_call(self.charge_off_call)
                logging.info("Charger turned off.")
            else:
                logging.warning("No charge_off_call specified.")
            if Params.get('global', 'local_execution') == '1':
                self._host_call('utilities\\MsgPrompt.exe -WaitForDC')
                logging.info("Charger unplugged.")

        time.sleep(int(self.delay))

    def testBeginCallback(self):
        pass

    def testEndCallback(self):
        pass

    def dataReadyCallback(self):
        if not self.conn_timeout:
            # Engage charging
            logging.info("Attempting to turn on charger...")
            if self.charge_on_call != "" and self.charge_on_call != None:
                self._host_call(self.charge_on_call)
                logging.info("Charger turned on.")
            else:
                logging.warning("No charge_on_call specified.")
            if Params.get('global', 'local_execution') == '1':
                self._host_call('utilities\\MsgPrompt.exe -WaitForAC')
                logging.info("Charger plugged in.")

    def testTimeoutCallback(self):
        logging.info("Attempting to turn on charger...")
        if self.charge_on_call != "" and self.charge_on_call != None:
            self._host_call(self.charge_on_call)
            logging.info("Charger turned on.")
        else:
            logging.warning("No charge_on_call specified.")
        if Params.get('global', 'local_execution') == '1':
            self._host_call('utilities\\MsgPrompt.exe -WaitForAC')
            logging.info("Charger plugged in.")
        self.conn_timeout = True
    
    def cleanup(self):
        logging.debug("Cleanup")
        self.dataReadyCallback()
