# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    # Params.setDefault('teams', 'maintain_bots', '0', desc='Periodically check the count of bots in the call and add additional if needed.', valOptions=['0', '1'])
    return

def run_user_only():
    import_run_user_only('scenarios\\macos\\_library\\Teams\\teams_setup')
    import_run_user_only('scenarios\\macos\\_library\\Teams\\teams_teardown')
    import_run_user_only('scenarios\\macos\\_library\\misc\\call_early_callback')
    Params.setUserDefault('teams', 'duration', '600', desc='Sets the time in seconds for the test to run.', valOptions=['60', '120', '240', '300', '600', '900'])
    Params.setUserDefault('teams', 'maintain_bots', '0', desc='Set to 1 to have the test periodically check that all bots are present in the call and add bots if needed.', valOptions=['0', '1'])
    return
