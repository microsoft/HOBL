# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Prep a DUT before testing
#   
##

from builtins import str
from builtins import range
from core.parameters import Params
from core.app_scenario import Scenario
import core.app_scenario
import logging
import os
import time
import threading
import core.call_rpc as rpc

class ProcessIdleTasks(core.app_scenario.Scenario):
    '''
    Preforms various tasks that prepare a device for testing.  This includes queuing background maintenance tasks in Windows so they will not be running during tests.  To ensure consistent results, please run this scenario at least once per day on devices before starting tests.
    '''
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'timeout', '1800', desc="Maximum time in seconds the automation will wait for tasks to complete") # 30 minutes = 1800 sec, 2 hr = 7200 sec
    Params.setDefault(module, "loops", "3", desc="Number of times the automation will attempt to perform tasks")
    Params.setDefault(module, 'run_idle_tasks', '1', desc="Queues Windows idle tasks so they will not be running during tests", valOptions=["0", "1"])
    Params.setDefault(module, 'final_reboot', '1', desc="Sets if the device will reboot at the conclusion of process_idle_tasks", valOptions=["0", "1"])

    run_idle_tasks = Params.get(module, 'run_idle_tasks')

    timeout = int(Params.get(module, 'timeout'))
    loops = int(Params.get(module, 'loops'))
    final_reboot = Params.get(module, 'final_reboot')
    reboot_complete = False

    # Params.setOverride("global", "collection_enabled", "0")
    Params.setOverride("global", "prep_tools", "")
    is_prep = True


    def runTest(self):
        if self.dut_ip == "127.0.0.1":
            self.loops = 1
        
        #logging.info("Setup")
        self._upload("utilities\\open_source\\process_idle_tasks.ps1", self.dut_exec_path)
        #logging.info("Initial Thread timeout - " + str(self.timeout / 60) + " min.")
        self._call(["powershell.exe", 'set-executionpolicy unrestricted -Force'], expected_exit_code="", fail_on_exception=False)


        tThread = ProcessIdleTasks.timerThread(self.timeout, self.loops, self)
        tThread.start()

        success = False
        for i in range(1, self.loops + 1):
                 
            try:
                logging.info("Calling process_idle_tasks.ps1, Attempt: " + str(i) + " Timeout: " + str((self.timeout)/ 60) + " minutes")
                self._call(["powershell.exe", os.path.join(self.dut_exec_path,"process_idle_tasks.ps1") + " -run_idle_tasks " + self.run_idle_tasks], timeout=self.timeout)
                success = True
                break
            except KeyboardInterrupt:
                tThread.kill()
            except:
                logging.info("process_idle_tasks call expired")
                while (self.reboot_complete == False):
                    time.sleep(1)
                # Reset flag
                logging.debug ("Reboot complete")
                self.reboot_complete = False

        tThread.event.set()
        if self.final_reboot == "1":
            logging.info("Final reboot")
            self._dut_reboot()
        if success:
            logging.info("process_idle_tasks complete")
        else:
            logging.info("process_idle_tasks did not complete, quitting")

    def tearDown(self):
        self.createPrepStatusControlFile()
        core.app_scenario.Scenario.tearDown(self)

    class timerThread(threading.Thread):
        def __init__(self, timeout, loops, scenario):
            threading.Thread.__init__(self)
            self.timeout = timeout
            self.loops = loops
            self.scenario = scenario
            self.event = threading.Event()
            self.setDaemon(True)
        
        def run(self):
            timeout_reset = self.timeout
            for i in range(self.loops):
                logging.info("Watchdog waiting for " + str((timeout_reset / 60)) + " minutes")
                while self.timeout > 0:   
                    if self.event.is_set():
                        return 
                    logging.info(str((self.timeout / 60)) + " minutes remaining")
                    time.sleep(60)
                    self.timeout -= 60
                logging.info("Timeout expired")
                # rebootDut(self, self.scenario)
                self.scenario._dut_reboot()
                time.sleep(10)
                self.scenario.reboot_complete = True
                timeout_reset = timeout_reset * 2
                self.timeout = timeout_reset
                self.scenario.timeout = timeout_reset
                # 2s delay to make sure ps1 script gets launched before we start new loop here.
                time.sleep(2)

        def kill(self):
            pass
       
def rebootDut(self, scenario):
    logging.info("Rebooting DUT")
    try:
        scenario._call(["cmd.exe",  "/C shutdown.exe /r /f /t 5"])
    except:
        pass
    time.sleep(20)
    scenario._wait_for_dut_comm()
    logging.info("Reboot complete")
    return


