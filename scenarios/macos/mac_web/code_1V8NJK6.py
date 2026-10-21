# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1V8NJK6.py')
    home_dir = scenario._call(["bash", "-c \"echo $HOME\""], expected_exit_code="").strip()
    safari_preferences = f"{home_dir}/Library/Preferences/com.apple.Safari.plist"
    output = scenario._call(["plutil", f'-p "{safari_preferences}"'], expected_exit_code="")

    if "Clear History..." not in output:
        logging.error('Clear History... shortcut key is not set. Please refer to Mac Setup Readme for instructions. https://github.com/microsoft/HOBL/blob/main/docs/support/docs/HOBL_Setup.md#dut-setup-for-macos')
        scenario.fail("Clear History... shortcut key is not set. Please refer to Mac Setup Readme for instructions. https://github.com/microsoft/HOBL/blob/main/docs/support/docs/HOBL_Setup.md#dut-setup-for-macos")
    scenario._sleep_to_now()