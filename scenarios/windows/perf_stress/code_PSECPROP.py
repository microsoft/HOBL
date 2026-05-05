# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#
# code_PSECPROP.py - Propagate cross-section parameters that ScenarioMaker UI
# cannot express:
#   1. perf_stress:bg_edge_tab_loops -> web_bg_tabs:bg_tab_loops
#      (No UI for cross-section setParam, so we do it here.)
#
# Run as the FIRST runtime action in perf_stress (right after Set Default
# nodes) so values are in place before any included library reads them.

import logging
from core.parameters import Params


def run(scenario):
    logging.debug('Executing code block: code_PSECPROP.py (cross-section param propagation)')

    bg_loops = Params.get('perf_stress', 'bg_edge_tab_loops')
    if bg_loops:
        Params.setParam('web_bg_tabs', 'bg_tab_loops', bg_loops)
        logging.info(
            "Propagated perf_stress:bg_edge_tab_loops=%s -> web_bg_tabs:bg_tab_loops",
            bg_loops,
        )
