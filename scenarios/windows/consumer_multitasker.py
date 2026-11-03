# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import scenarios.windows.enterprise_collab
from parameters import Params
Params.setParam("enterprise_collab", "minwin_workloads", "productivity file_explorer")
Params.setParam("enterprise_collab", "simple_office_launch", "0")

class MinCP_Workload_All(scenarios.windows.enterprise_collab.EnterpriseCollab):
    '''
    Microsoft Teams video call with 9 bot participants.
    Local camera and mic are on, other 9 participants are bots sending video and audio.
    '''
    pass