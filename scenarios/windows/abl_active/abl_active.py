# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import core.app_scenario
from core.parameters import Params
import logging
import time
import os
from . import default_params


class AblActive(core.app_scenario.Scenario):
    # Set default parameters:
    default_params.run()

    prep_scenarios = ["edge_install", "web_prep", "office_install", "onedrive_prep", "productivity_prep"]

    actions = None

    def setUp(self):
        # Load actions JSON.
        actions_json = os.path.join(os.path.dirname(__file__), "abl_active.json")
        self.actions = self.load_action_json(actions_json)

        # Execute Setup actions, if they exist
        setup_action = self._find_next_type("Setup", json=self.actions)
        if setup_action:
            self.run_actions(setup_action["children"])

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def runTest(self):
        # Execute Run Test actions, if they exist
        runtest_action = self._find_next_type("Run Test", json=self.actions)
        if runtest_action:
            self.run_actions(runtest_action["children"])
            return
        
        # If no "Run Test", "Setup", or "Teardown" specified, then just execute the whole list
        setup_action = self._find_next_type("Setup", json=self.actions)
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if not runtest_action and not setup_action and not teardown_action:
            self.run_actions(self.actions)


    def tearDown(self):
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        # Execute Teardown actions, if they exist
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if teardown_action:
            self.run_actions(teardown_action["children"])

    
    def kill(self):
        # In case of scenario failure or termination, kill any applications left open here:

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

        # Kill office apps
        try:
            self._kill("Outlook.exe Excel.exe Powerpnt.exe Winword.exe OneNote.exe")
        except:
            pass

        return