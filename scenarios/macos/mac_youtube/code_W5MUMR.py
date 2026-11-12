# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import core.call_rpc as rpc

def run(scenario):
    logging.debug('Executing code block: code_W5MUMR.py')
    rpc.plugin_call(scenario.dut_ip, scenario.rpc_port, "InputInject", "MoveTo", 0, 500, scenario.current_screen, scenario.cursor_movement_enable)