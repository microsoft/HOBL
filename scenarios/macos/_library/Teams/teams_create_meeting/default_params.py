# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from functools import partial
import os
from core.parameters import Params
import utilities.open_source.modules

import_run_user_only = partial(utilities.open_source.modules.import_run_user_only, here=__file__)

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    return

def run_user_only():
    Params.setUserDefault('teams', 'meeting_time', '0', desc='Set the time in minutes that the meeting can last up to. Default is 120min.', valOptions=[])
    Params.setUserDefault('teams', 'access_key', '-1', desc='The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key.', valOptions=[])
    Params.setUserDefault('teams', 'number_of_bots', '1', desc='Sets the number of bots to have in the meeting.', valOptions=['1', '2', '4', '8', '9'])
    Params.setUserDefault('teams', 'bots_send_video', '1', desc='Set to 1 if bots should have their cameras on. Set to 0 for audio only calls.', valOptions=['0', '1'])
    Params.setUserDefault('teams', 'bots_send_audio', '1', desc='Set to 1 to have bots send audio. Set to 0 to have bots be muted.', valOptions=['0', '1'])
    Params.setUserDefault('teams', 'bots_share_screen', '0', desc='Set to 1 to have the primary bot share its screen in the meeting.', valOptions=['0', '1'])
    Params.setUserDefault('teams', 'bots_test_server', '0', desc='For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use.', valOptions=['0', '1'])
    Params.setUserDefault('teams', 'duration', '600', desc='Duration of the Teams call to be recorded in seconds. Limit of 600s per call.', valOptions=['30', '60', '120', '300', '600'])
    return
