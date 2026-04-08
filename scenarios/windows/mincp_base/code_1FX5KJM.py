# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import logging

from parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1FX5KJM.py')
    semantic_index_status = scenario._call(["cmd.exe", '/C @for /f "skip=2 tokens=3" %A in (\'reg query "HKLM\\SOFTWARE\\Microsoft\\Windows Search\\SemanticIndexer" /v SemanticIndexingStatus\') do @set /a %A'], expected_exit_code="")
    logging.info("Semantic Index Status is %s", semantic_index_status)
    scenario._upload("utilities\\proprietary\\IndexUpdater\\IndexUpdater.exe", scenario.dut_exec_path)
    scenario._upload("utilities\\proprietary\\IndexUpdater\\IndexUpdater.dll", scenario.dut_exec_path)
    scenario._upload("utilities\\proprietary\\IndexUpdater\\IndexUpdater.runtimeconfig.json", scenario.dut_exec_path)
    scenario._upload("utilities\\proprietary\\IndexUpdater\\IndexUpdater.deps.json", scenario.dut_exec_path)
    semantic_index_testdrive = os.path.join(scenario.dut_exec_path, "semantic_testdrive")
    scenario._remote_make_dir(semantic_index_testdrive)
    Params.setParam("enterprise_collab",'semantic_index_testdrive', semantic_index_testdrive)
    index_updater_path = os.path.join(scenario.dut_exec_path, "IndexUpdater.exe")
    update_command = f'add "{semantic_index_testdrive}"'
    semantic_index_update_result = scenario._call([index_updater_path, update_command])
    logging.info("Semantic Index Update Result: %s", semantic_index_update_result)
    abl_docs_dir = os.path.join("scenarios", "windows", "_library", "productivity", "prod_setup", "abl_docs")
    for filename in os.listdir(abl_docs_dir):
        filepath = os.path.join(abl_docs_dir, filename)
        if os.path.isfile(filepath):
            scenario._upload(filepath, semantic_index_testdrive)
            logging.info("Uploaded %s to semantic_index_testdrive", filename)
