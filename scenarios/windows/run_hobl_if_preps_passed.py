# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Check if rundown_abl_prep scenarios have all passed, and if so, launch rundown_abl plan
##

import core.app_scenario
from core.parameters import Params
import fnmatch
import os
import requests
import logging
import core.arguments
from urllib.parse import (
    urlparse,
    urlunparse,
    urlencode
)

class RunAblIfPrepsPassed(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    dashboard_url = Params.get('global', 'dashboard_url')
    dut_architecture = Params.get('global', 'dut_architecture')
    study_type = Params.getOverride('global', 'study_type')

    is_prep = True


    def setUp(self):
        # Don't call base setUp so that we don't interact with DUT
        return


    def runTest(self):
        prep_scenarios = ["productivity_prep", "button_install", "edge_install", "msa_prep", "onedrive_prep", "daily_prep", "config_check", "store_prep", "adaptive_color_disable", "teams_install", "lvp_prep", "cs_floor_prep"]
        # Check if preps ran
        assert_list = ""
        assert_list += self.checkPrepStatus(prep_list)

        if assert_list != "":
            self._assert(assert_list)
        else:
            # All preps passed, launch abl rundown
            args = core.arguments.args
            params_file = args.profile
            profile = os.path.basename(params_file).rsplit('.',1)[0]

            url = urlunparse(
                urlparse(self.dashboard_url)._replace(
                    path="/plan/RunPlan"
                )
            )

            study_type_param = ""

            if self.study_type:
                study_type_param = f"&studyType={self.study_type}"

            response = requests.get(url + "?profile=" + profile + "&plan=hobl.ps1" + study_type_param)
            logging.info("Launching hobl.ps1 for profile " + profile + ": " + str(response))
            if self.dut_architecture.lower() == "x64":
                response = requests.get(url + "?profile=" + profile + "&plan=hobl_23_phm.ps1" + study_type_param)
                logging.info("Launching hobl_phm.ps1 for profile " + profile + ": " + str(response))
            response = requests.get(url + "?profile=" + profile + "&plan=hobl_etl.ps1" + study_type_param)
            logging.info("Launching hobl_etl.ps1 for profile " + profile + ": " + str(response))



    def tearDown(self):
        # Don't call base tearDown so that we don't interact with DUT
        return


    def kill(self):
        # Prevent base kill routine from running
        return 0
