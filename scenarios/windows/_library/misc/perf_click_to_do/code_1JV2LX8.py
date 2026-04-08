import logging
import time

def run(scenario):
    logging.debug('Executing code block: code_1JV2LX8.py')
    

    """
    Setup PerfTrack monitoring:
    - Upload UtcPerftrack XML and DisableAllUploads.json
    - Set registry keys for full telemetry
    - Restart DiagTrack to force fresh scenario loading
    """
    logging.debug('Executing code block: code_setup_perf.py')

    # Upload PerfTrack scenario definitions
    scenario._upload("utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload", check_modified=False)
    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload", check_modified=False)

    # Enable full telemetry collection (level 3 = Full)
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])

    # Disable WER uploads
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])

    # Restart DiagTrack to force fresh scenario loading (resets throttling)
    logging.info("Restarting DiagTrack service")
    scenario._call(["cmd.exe", '/C net stop diagtrack >nul 2>&1 & net start diagtrack >nul 2>&1'])
    time.sleep(10)

    scenario._sleep_to_now()
