# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os

def run(scenario):
    logging.debug('Executing code block: code_1L99AYH.py')
    webxprt_score = scenario._call(["powershell", "Get-Clipboard"])

    # separater by new line and take the line after "score"
    score = webxprt_score.split("\n")[5]
    logging.info("WebXPRT Score: " + score)

    webxprt_score_txt = os.path.join(scenario.result_dir, "webxprt_score.txt")
    with open(webxprt_score_txt, "w") as f:
        f.write("WebXPRT Score: " + score)
