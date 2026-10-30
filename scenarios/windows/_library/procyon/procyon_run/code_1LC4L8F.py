# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import time
import math
import xml.etree.ElementTree as ET
import pandas as pd
from core.parameters import Params

lookup = [
    ("OfficeProductivity",                    "office_productivity.def"),
    ("MultiPlatform",                         "office_productivity_mp.def"),
    ("Essentials",                            "essentials.def"),
    ("Battery",                               "video_playback_batterylife.def"),
    ("Photo",                                 "photo_editing.def"),
    ("Video",                                 "video_editing.def"),
    ("AI Computer Vision WinML",              "ai_computer_vision_winml.def"),
    ("AI Computer Vision SNPE",               "ai_computer_vision_snpe.def"),
    ("AI Computer Vision OpenVino",           "ai_computer_vision_openvino.def"),
    ("AI Computer Vision TensorRT",           "ai_computer_vision_tensorrt.def"),
    ("AI Computer Vision RyzenAI",            "ai_computer_vision_ryzenai.def"),
    ("AI Computer Vision CoreML All FP16",    "ai_computer_vision_coreml_all_fp16.def"),
    ("AI Computer Vision CoreML All FP32",    "ai_computer_vision_coreml_all_fp32.def"),
    ("AI Computer Vision CoreML All Integer", "ai_computer_vision_coreml_all_integer.def"),
]

def get_definition(test):
    if test.endswith(".def"):
        return test

    for key, definition in lookup:
        if key in test:
            return definition

    return test

def is_float(string):
    try:
        float(string)
        return True
    except ValueError:
        return False

def run(scenario):
    logging.debug('Executing code block: code_1LC4L8F.py')

    test_def = get_definition(Params.get('procyon', 'test'))
    loop_num = Params.get('procyon', 'loop_number')

    if loop_num is None or loop_num == "":
        loop_num = "1"
    loop_num = int(float(loop_num))

    logging.info(f"Running Procyon loop {loop_num} using test definition: {test_def}")

    if scenario.platform.lower() == "macos":
        target           = f"{scenario.dut_exec_path}/procyon_resources"
        procyon_out_dir  = f"{scenario.dut_data_path}/procyon"
        procyon_call_cmd = ["zsh", f"{target}/mac_procyon_run.sh {test_def} {procyon_out_dir}/Results_{loop_num}.xml"]
    else:
        procyon_out_dir  = os.path.join(scenario.dut_data_path, "procyon")
        procyon_call_cmd = [
            "C:\\Program Files\\UL\\Procyon\\ProcyonCmd.exe",
            f"--definition={test_def} --loop=1 --export-xml={procyon_out_dir}\\Results_{loop_num}.xml"
        ]

    scenario._remote_make_dir(procyon_out_dir, delete=True)
    scenario._call(procyon_call_cmd, timeout=3600*3, fail_on_exception=False)

    timestamp = math.ceil(time.time() - scenario.scenario_start_time)

    scenario._copy_data_from_remote(os.path.join(scenario.result_dir, "procyon"), procyon_out_dir)
    xml_file = os.path.join(scenario.result_dir, "procyon", f"Results_{loop_num}.xml")

    if not os.path.exists(xml_file):
        scenario.error_fail(f"Result file not found: {xml_file}")

    tree         = ET.parse(xml_file)
    root         = tree.getroot()
    first_result = root.find(".//result")

    scores_dict = {"Timestamp": timestamp}

    if first_result is not None:
        for element in first_result.iter():
            tag = element.tag
            if tag.endswith("Score") and is_float(element.text):
                scores_dict[tag] = float(element.text)

    if len(scores_dict) == 1:
        scenario.error_fail(f"No score tags found in XML file: {xml_file}")

    csv_file = os.path.join(scenario.result_dir, "procyon", "Procyon_Results.trace")

    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)

        existing_cols = list(df.columns)

        for col in scores_dict:
            if col not in existing_cols:
                df[col] = ""
                existing_cols.append(col)

        scores_dict = {col: scores_dict.get(col, "") for col in existing_cols}

        df = pd.concat([df, pd.DataFrame([scores_dict])], ignore_index=True)
        df.to_csv(csv_file, index=False)
    else:
        df = pd.DataFrame([scores_dict])
        df.to_csv(csv_file, index=False)

    summary_file = os.path.join(scenario.result_dir, "Procyon_Summary.csv")

    avg_df = (
        df.drop(columns=["Timestamp"], errors="ignore")
        .mean(numeric_only=True)
        .reset_index()
    )

    avg_df["index"] = "Procyon-" + avg_df["index"].astype(str)
    avg_df[0]       = avg_df[0].round().astype("int64")

    avg_df.to_csv(summary_file, index=False, header=False)
