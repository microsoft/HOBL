import logging

def run(scenario):
    logging.debug('Executing code block: code_1JV2P4M.py')
    """
    Teardown PerfTrack monitoring:
    - Keep telemetry at full level for consistent PerfTrack between runs
    - Keep sideloaded files so DiagTrack stays loaded
    """
    logging.debug('Executing code block: code_teardown_perf.py')

    # Don't reset telemetry or delete sideloaded files
    # DiagTrack needs level 3 and the sideloaded XML to fire PerfTrack scenarios consistently
