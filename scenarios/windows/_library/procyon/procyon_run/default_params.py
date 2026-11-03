# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    return

def run_user_only():
    Params.setUserDefault('procyon', 'test', 'OfficeProductivity', desc='Workload to run', valOptions=['OfficeProductivity', 'MultiPlatform', 'Essentials', 'BatteryLife', 'PhotoEditing', 'VideoEditing', 'AI Computer Vision WinML', 'AI Computer Vision SNPE (QC 8cx Gen3 min)', 'AI Computer Vision OpenVino (Intel)', 'AI Computer Vision TensorRT (NVIDIA)', 'AI Computer Vision RyzenAI (AMD)', 'AI Computer Vision CoreML All FP16', 'AI Computer Vision CoreML All FP32', 'AI Computer Vision CoreML All Integer'])
    return
