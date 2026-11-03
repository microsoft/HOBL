# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import scenarios.windows.cm_base
from parameters import Params
Params.setParam("cm_base", "minwin_workloads", "productivity file_explorer")

class MinCP_Workload_All(scenarios.windows.cm_base.CmBase):
    
    pass