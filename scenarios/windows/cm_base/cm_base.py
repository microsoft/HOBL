# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import core.app_scenario
from core.parameters import Params
import logging
import os
from . import default_params
import time

# Description:
#   Automatically generated standard scenario.

class CmBase(core.app_scenario.Scenario):
    prep_scenarios = ["edge_install", "web_prep", "office_install", "onedrive_prep", "productivity_prep"]

    # Set default parameters:
    default_params.run()

    module = __module__.split('.')[-1]

    if Params.get(module, "perf_run") == "1":
        logging.info("Adding perf_utc tool for parsing perf metrics")
        Params.setParam("global", "tools", "+perf_utc")

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
        try:
            # Stop measurement before closing applications.
            core.app_scenario.Scenario.tearDown(self)
            teardown_action = self._find_next_type("Teardown", json=self.actions)
            if teardown_action is not None:
                self.run_actions(teardown_action["children"])
        finally:
            self.kill()


    def kill(self):
        """Clean up after any stopping point, including failed setup or teardown."""
        cleanup_steps = [
            ("dismiss Start menu and overlays", lambda: self._send_text("\ue00c\ue00c")),
            # Close folder windows without terminating the Explorer desktop shell.
            ("close File Explorer windows", lambda: self._call([
                "powershell.exe",
                '-NoProfile -Command "$ErrorActionPreference = \'Stop\'; '
                '$shell = New-Object -ComObject Shell.Application; '
                '@($shell.Windows()) | ForEach-Object { '
                'if ([System.IO.Path]::GetFileName($_.FullName) -ieq \'explorer.exe\') '
                '{ $_.Quit() } }"'
            ])),
            ("close Task Manager", lambda: self._kill("Taskmgr.exe")),
            ("close Snipping Tool", lambda: self._kill("SnippingTool.exe")),
            ("close workload applications", self._kill_applications),
            ("restore perf configuration", self._perf_teardown),
        ]
        for description, cleanup in cleanup_steps:
            try:
                cleanup()
            except Exception:
                logging.exception("cm_base cleanup failed: %s", description)


    def _perf_teardown(self):
        if Params.get(self.module, "perf_run") == "1":
            path = os.path.join(
                os.path.dirname(__file__), "..", "_library", "enterprise_collab",
                "perf_teardown", "perf_teardown.json"
            )
            self.run_actions(self.load_action_json(path))


    def _kill_applications(self):
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
        try:
            self._web_replay_kill()
        except Exception:
            logging.exception("cm_base cleanup failed: stop web replay")

        time.sleep(3)
        #Kill Timers
        try:
            self._kill("SimpleTimer.exe")
        except:
            pass

        # Kill office apps
        try:
            self._kill("olk.exe Excel.exe Powerpnt.exe Winword.exe")
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
