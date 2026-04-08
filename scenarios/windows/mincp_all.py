# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from parameters import Params
Params.setParam("mincp_base", "mincp_workloads", "copilot_query semantic_search click_todo productivity file_explorer start_launch")
Params.setParam("enterprise_collab", "mincp_workloads", "copilot_query semantic_search click_todo productivity file_explorer start_launch")
Params.setParam("mincp_base", "simple_office_launch", "0")
import scenarios.windows.mincp_base
class MinCP_Workload_All(scenarios.windows.mincp_base.MincpBase):
    '''
    Microsoft Teams video call with 9 bot participants.
    Local camera and mic are on, other 9 participants are bots sending video and audio.
    '''
    pass