# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os

from core.parameters import Params


def run(scenario):
    logging.debug('Executing code block: code_V4J32J.py')

    if Params.get("global", "local_execution") == "0":
        userprofile = scenario._call(["cmd.exe", "/C echo %USERPROFILE%"]).strip()
    else:
        userprofile = os.environ["USERPROFILE"]

    abl_docs_path = os.path.join(userprofile, "abl_docs")
    scenario._call(
        ["cmd.exe", f'/C if exist "{abl_docs_path}" rmdir /S /Q "{abl_docs_path}"'],
        expected_exit_code="",
        fail_on_exception=False,
    )

    try:
        logging.debug("Killing Outlook.exe Excel.exe Powerpnt.exe Winword.exe OneNnote.exe")
        scenario._kill("Outlook.exe Excel.exe Powerpnt.exe Winword.exe OneNote.exe")
    except:
        pass
