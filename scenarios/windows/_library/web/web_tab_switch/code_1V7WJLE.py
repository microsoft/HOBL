# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1V7WJLE.py')
    archive_name = Params.get('web_tab_switch', 'archive_name')
    scenario._web_replay_change_archive(archive_name)