# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os

import core.app_scenario
import core.call_rpc as rpc
from scenarios.windows._library.responsiveness.pictures_fixture import (
    ensure_pictures_fixture,
)
from scenarios.windows._library.responsiveness import machine_profiles

from . import default_params


class ProductivityAnnoyance(core.app_scenario.Scenario):
    default_params.run()

    prep_scenarios = ["office_install", "onedrive_prep", "productivity_prep"]

    actions = None

    def setUp(self):
        machine_profiles.apply_to_mute("productivity_annoyance")
        rpc.plugin_load(
            self.dut_ip,
            self.rpc_port,
            "InputInject",
            "InputInject.Application",
            "C:\\hobl_bin\\InputInject\\InputInject.dll",
        )
        ensure_pictures_fixture(self)

        actions_json = os.path.join(
            os.path.dirname(__file__),
            "productivity_annoyance.json",
        )
        self.actions = self.load_action_json(actions_json)

        setup_action = self._find_next_type("Setup", json=self.actions)
        if setup_action:
            self.run_actions(setup_action["children"])

        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        runtest_action = self._find_next_type("Run Test", json=self.actions)
        if runtest_action:
            self.run_actions(runtest_action["children"])
            return

        setup_action = self._find_next_type("Setup", json=self.actions)
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if not runtest_action and not setup_action and not teardown_action:
            self.run_actions(self.actions)

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)

        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if teardown_action:
            self.run_actions(teardown_action["children"])

    def kill(self):
        try:
            self._kill(
                "Outlook.exe Excel.exe Powerpnt.exe Winword.exe OneNote.exe"
            )
        except Exception:
            pass