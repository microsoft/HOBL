# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
from core.parameters import Params

def run(scenario):
    logging.debug(f'Executing code block: code_URXKA1.py at: {__file__}')
    module_folder = os.path.dirname(__file__)
    
    typing_delay = int(Params.get('global', 'typing_delay'))
    # Honor [short_typing] (Set Default 0 in prod_excel_run.json) the same way
    # prod_word_run / prod_outlook_run do. perf_stress sets short_typing=1.
    # section=None walks scenario_section -> global, matching how JSON resolves [short_typing].
    short_val = Params.get(None, 'short_typing')
    short = (short_val == '1')
    size = 10 if short else 21
    index = 0
    typing_str = ""
    with open(os.path.join(module_folder, "TestBookData.txt"), 'r') as myfile:
        data=myfile.read().split()

    for a in range (0, size):
        typing_str = ""
        x = data[index]
        y = data[index + 1]
        # scenario._sleep_by(1.0)
        typing_str += x
        typing_str += '\ue014'  # RIGHT
        # Insert averaging at after run 10, 20, ...
        if a > 9 and a % 10 == 0:
            typing_str += "=AVERAGE(OFFSET(INDIRECT(ADDRESS(ROW(),COLUMN())),-10,0,10,1))"          
        else:
            typing_str += y
        typing_str += '\n'
        typing_str += '\ue012'  # LEFT
        index += 2
        scenario._send_text(typing_str, typing_delay)
        typing_str_delay = (len(typing_str) * typing_delay) / 1000
        typing_str_delay = round(typing_str_delay * 2) / 2  # round to nearest 0.5
        scenario._sleep_by(typing_str_delay + 2)
