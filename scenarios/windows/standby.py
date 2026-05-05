# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from parameters import Params
Params.setParam("cs_floor", "connection", "Connected")

import scenarios.windows.cs_floor

class Standby(scenarios.windows.cs_floor.CS):
    '''
    Puts the device into standby mode, still conneccted to the network.
    '''
    pass