# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params
import os
import time

def run(scenario):
    logging.debug('Executing code block: code_UTAWXA.py')
    
    office_theme = Params.get('global', 'office_theme')
    if office_theme == "Colorful":
        office_theme_val = '0'
    elif office_theme == "Dark Gray":
        office_theme_val = '3'
    elif office_theme == "Black":
        office_theme_val = '4'
    elif office_theme == "White":
        office_theme_val = '5'
    elif office_theme == "System":
        office_theme_val = '6'

    # Set Office theme, if specified
    if office_theme != "Don't Change":
        scenario._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common" /v "UI Theme" /t REG_DWORD /d ' + office_theme_val + ' /f > null 2>&1'])
        regpath = scenario._call(["cmd.exe", '/C reg query "HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\Roaming\\Identities"'], expected_exit_code="")
        regpath = regpath.strip()
        reg_ary = regpath.split()
        if len(reg_ary) > 0:
            regpath = reg_ary[0]
            if "Anonymous" in regpath and len(reg_ary) > 1:
                regpath = reg_ary[1]
        logging.debug(f"Office identity regpath: {regpath}")
        if regpath != "" and "ERROR" not in regpath:
            regpath = regpath + "\\Settings\\1186\\{00000000-0000-0000-0000-000000000000}"
            scenario._call(["cmd.exe", '/C reg add "' + regpath + '" /v "Data" /t REG_BINARY /d 0' + office_theme_val + '000000 /f > null 2>&1'])
        else:
            logging.warning("No Office identity found in registry.")

    # Get user profile folder
    if Params.get("global", "local_execution") == "0":
        userprofile = scenario._call(["cmd.exe", "/C echo %USERPROFILE%"])
    else:
        userprofile = os.environ['USERPROFILE']

    # Upload handle.exe
    # if not scenario._check_remote_file_exists("handle.exe"):
    #     scenario._upload("utilities\\proprietary\\handle.exe", scenario.dut_exec_path)

    # Create junction link to abl_docs, so less typing of paths
    onedrive_path = "c:\\abl_docs"
    scenario._call(["cmd.exe", "/C rmdir " + onedrive_path], expected_exit_code="", fail_on_exception=False)
    scenario._call(["cmd.exe", "/C mklink /J " + onedrive_path + ' "' + userprofile + '\\OneDrive\\abl_docs"'])

    # Upload Office docs
    upload_successful = False
    doc_source = os.path.join(os.path.dirname(__file__), "abl_docs")
    doc_dest = userprofile
    for i in range(12):
        try:
            scenario._upload(doc_source, doc_dest)
            upload_successful = True
            break
        except:
            logging.error("Could not copy productivity content to onedrive.")
            # handle_out = scenario._call([scenario.dut_exec_path + "\\handle.exe", "/accepteula " + userprofile + "\\OneDrive\\abl_docs"], expected_exit_code="")
            # for line in handle_out.split('\n'):
            #     logging.error(line.strip("\r\n"))
        time.sleep(10)
    if not upload_successful:
        logging.error("Could not copy productivity content to onedrive in 12 tries.")
        scenario.fail("Could not copy productivity content to onedrive in 12 tries.")
