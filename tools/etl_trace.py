# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Takes a provider or providers and passes that to DUT to get an etl trace

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import pandas as pd
import logging
import sys
import os
import re


class Tool(Scenario):
    '''
    Collect ETL trace from specified [providers].
    
    Collects ETL traces from the specified providers. Multiple providers can be specified, separated by spaces. 

    Parameters:
        providers: The ETL provider files to use (e.g., '@\\providers'). 
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'providers', '', desc="ETL provider files to use", valOptions=["@\\providers"], multiple=True)
    # Get parameters
    providers = Params.get(module, 'providers')

    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False


        logging.info("Etl Tracing Tool - initializing, associated with scenario: " + self.scenario._module)

        all_providers = Params.getCalculated('trace_providers')

        all_providers = all_providers + " " + self.providers
        Params.setCalculated('trace_providers', all_providers)
  
    def dataReadyCallback(self):
        return