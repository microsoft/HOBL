# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import core.app_scenario
from core.parameters import Params
import logging
import os
from . import default_params

# Description:
#   Automatically generated standard scenario.

class CmBase(core.app_scenario.Scenario):
    # Set default parameters:
    default_params.run()

    actions = None

    def setUp(self):
        # Load actions JSON.
        actions_json = os.path.join(os.path.dirname(__file__), "cm_base.json")
        self.actions = self.load_action_json(actions_json)

        # Execute Setup actions, if they exist
        setup_action = self._find_next_type("Setup", json=self.actions)
        if setup_action is not None:
            self.run_actions(setup_action["children"])

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def runTest(self):
        # Execute Run Test actions, if they exist
        runtest_action = self._find_next_type("Run Test", json=self.actions)
        if runtest_action is not None:
            self.run_actions(runtest_action["children"])
            return

        # If no "Run Test", "Setup", or "Teardown" specified, then just execute the whole list
        setup_action = self._find_next_type("Setup", json=self.actions)
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if runtest_action is None and setup_action is None and teardown_action is None:
            self.run_actions(self.actions)


    def tearDown(self):
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        # Execute Teardown actions, if they exist
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if teardown_action is not None:
            self.run_actions(teardown_action["children"])


    def kill(self):
        # In case of scenario failure or termination, kill any applications left open here:

        #Kill teams related processes
        try:
            if self.platform.lower() == "w365":
                self._run_with_inputinject("cmd.exe /c tasklist /nh /fo csv /fi \"IMAGENAME eq 'Video.UI.exe'\"")
            else:
                self._kill("Video.UI.exe")
        except:
            pass
        
        try:
            if self.platform.lower() == "w365":
                self._run_with_inputinject("cmd.exe /c tasklist /nh /fo csv /fi \"IMAGENAME eq 'Microsoft.Media.Player.exe'\"")
            else:
                self._kill("Microsoft.Media.Player.exe")
        except:
            pass

        try:
            if self.platform.lower() == "w365":
                self._run_with_inputinject("cmd.exe /c tasklist /nh /fo csv /fi \"IMAGENAME eq 'ms-teams.exe'\"")
            else:
                self._kill("ms-teams.exe", force = True)
        except:
            pass

        try:
            # Do it again because some windows can still be left open
            if self.platform.lower() == "w365":
                self._run_with_inputinject("cmd.exe /c tasklist /nh /fo csv /fi \"IMAGENAME eq 'ms-teams.exe'\"")
            else:
                self._kill("ms-teams.exe", force = True)
        except:
            pass

        time.sleep(3)
         # Kill web browser and web_replay
        try:
            self._kill("msedge.exe")
        except:
            pass
        try:
            self._kill("chrome.exe")
        except:
            pass

        time.sleep(3)
        self._web_replay_kill()

        time.sleep(3)
        #Kill Timers
        try:
            self._kill("SimpleTimer.exe")
        except:
            pass

        # Kill office apps
        try:
            self._kill("Outlook.exe Excel.exe Powerpnt.exe Winword.exe OneNote.exe")
        except:
            pass

        # Kill Powershell
        try:
            # self._kill("powershell.exe")
            logging.info("Logging here because Powershell kill is commented out")
            pass
        except:
            pass

        return
