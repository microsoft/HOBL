# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import time

import core.app_scenario
from core.parameters import Params
from scenarios.windows._library.responsiveness.pictures_fixture import (
    ensure_pictures_fixture,
)

from . import default_params


class IdleAnnoyance(core.app_scenario.Scenario):
    default_params.run()

    prep_scenarios = []
    actions = None

    def setUp(self):
        ensure_pictures_fixture(self)

        actions_json = os.path.join(os.path.dirname(__file__), 'idle_annoyance.json')
        self.actions = self.load_action_json(actions_json)

        if self.platform == 'Windows':
            self._call([
                'powershell.exe',
                '-NoProfile -Command "$shell = New-Object -ComObject Shell.Application; $shell.MinimizeAll()"',
            ])
        time.sleep(float(Params.get('idle_annoyance', 'desktop_settle_seconds')))

        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        runtest_action = self._find_next_type('Run Test', json=self.actions)
        if runtest_action:
            self.run_actions(runtest_action['children'])
            return
        self.run_actions(self.actions)

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)

    def kill(self):
        try:
            self._call([
                'powershell.exe',
                '-NoProfile -Command "$shell = New-Object -ComObject Shell.Application; $shell.MinimizeAll()"',
            ])
        except Exception:
            pass