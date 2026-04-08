"""
//--------------------------------------------------------------
//
// HOBL
// Copyright(c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files(the ""Software""),
// to deal in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and / or sell copies
// of the Software, and to permit persons to whom the Software is furnished to do so,
// subject to the following conditions :
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
// FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE AUTHORS
// OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
// WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF
// OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//
//--------------------------------------------------------------
"""

import scenarios.app_scenario
from parameters import Params
import logging
import os
from . import default_params

# Description:
#   Type-to-Search via taskbar search icon

class SearchTaskbar(scenarios.app_scenario.Scenario):
    # Set default parameters:
    default_params.run()

    actions = None

    def setUp(self):
        # Load actions JSON.
        actions_json = os.path.join(os.path.dirname(__file__), "search_taskbar.json")
        self.actions = self.load_action_json(actions_json)

        # Execute Setup actions, if they exist
        setup_action = self._find_next_type("Setup", json=self.actions)
        if setup_action is not None:
            self.run_actions(setup_action["children"])

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        scenarios.app_scenario.Scenario.setUp(self)


    def runTest(self):
        # Execute Run Test actions, if they exist
        run_action = self._find_next_type("Run Test", json=self.actions)
        if run_action is not None:
            self.run_actions(run_action["children"])


    def tearDown(self):
        # Execute Teardown actions, if they exist
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if teardown_action is not None:
            self.run_actions(teardown_action["children"])

        # Call base class tearDown() for clean up
        scenarios.app_scenario.Scenario.tearDown(self)
