# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import core.call_rpc as rpc
import logging

def run(scenario):
    logging.debug('Executing code block: code_UCL6HH.py')
    rpc.plugin_call(scenario.dut_ip, scenario.rpc_port, "InputInject", "MoveTo", 100, 500, scenario.current_screen)