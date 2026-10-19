# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool wrapper for audio control

from builtins import str
from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os
import decimal


class Tool(Scenario):
    '''
    Set specified audio volume.

    Setting the 'volume' parameter will adjust the audio output volume accordingly.

    Parameters:
        volume: The desired audio output volume as a percentage (0-100).
    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'volume', 'Unknown')
    #Params.setDefault(module, 'mute', "False")

    # Get parameters
    volume = Params.get(module, 'volume')
    #mute = Params.get(module, 'mute')

    def initCallback(self, scenario):

        self.scenario = scenario
        if self.volume == "Unknown":
            logging.error("Could not resolve specified volume parameter.")
            self.fail("Could not resolve specified volume parameter.")

        self.set_vol = (decimal.Decimal(self.volume) / 100)
        
        if self.platform.lower() == "macos":
            self._call(["zsh", f"-c \"osascript -e 'set volume output volume {self.volume}'\""])
            logging.info("Audio volume set to: " + str(self.volume))
            return
        
        elif self.platform.lower() == "windows":

            # exists = os.path.isfile(self.dut_exec_path)
            exists = os.path.isfile(self.dut_exec_path + "\\audio_volume.ps1")
            if exists:
                pass
            else:
                self._upload("utilities\\open_source\\audio_volume.ps1", self.dut_exec_path)
            
            self._call(["powershell.exe ", self.dut_exec_path + "\\audio_volume.ps1 " +  str(self.set_vol)])
            logging.info("Audio volume set to: " + str(self.set_vol))
            return

    def testBeginCallback(self):
        pass

    def testEndCallback(self):
        pass

    def dataReadyCallback(self):
        pass



