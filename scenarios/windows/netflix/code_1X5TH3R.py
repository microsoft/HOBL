# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1X5TH3R.py')
    scenario._call(["powershell.exe", "Set-Clipboard -Value $null"])
