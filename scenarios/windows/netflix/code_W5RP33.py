# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import configparser
import json
import csv

def run(scenario):
    logging.debug('Executing code block: code_W5RP33.py')

    hud_content = scenario._call(["powershell", "Get-Clipboard"])

    section = "global"

    hud_content = f"[{section}]\n{hud_content}"

    config = configparser.RawConfigParser() # strict=False to allow duplicates

    try:
        config.read_string(hud_content)
    except:
        scenario.fail("Unable to save video information")

    file_path_json = os.path.join(scenario.result_dir, "netflix_video_info.json")
    file_path_csv  = os.path.join(scenario.result_dir, "netflix_video_info_rollup.csv")

    items = dict(config.items(section))

    if "video track" in items:
        with open(file_path_json, 'w') as f:
            json.dump(
                items,
                f,
                indent=4,
                sort_keys=True
            )

        with open(file_path_csv, 'w') as f:
            writer = csv.writer(
                f,
                delimiter=',',
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL,
                lineterminator="\n"
            )

            rate_info = items["playing bitrate (a/v)"]

            if all(x in rate_info for x in ["(", ")"]):
                resolution = rate_info[rate_info.find("(")+1:rate_info.find(")")]
            else:
                resolution = rate_info

            writer.writerow(["Netflix Resolution", resolution])
            writer.writerow(["Netflix Codec",      items["video track"]])

            # 150 is the starting video time in seconds
            writer.writerow(["Netflix Duration (sec)", round(float(items["position"]) - 150, 3)])
    else:
        scenario.fail(
            "Unable to save video information. Data obtained is invalid"
        )
