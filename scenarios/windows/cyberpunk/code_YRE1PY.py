# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params
import os

def run(scenario):
    logging.debug('Executing code block: code_YRE1PY.py')
    game_location = Params.get('cyberpunk', 'game_location')
    benchmark_loops = Params.get('cyberpunk', 'benchmark_loops')
    graphics_settings = Params.get('cyberpunk', 'graphics_settings')
    cyberpunk_executable = os.path.join(game_location, "bin", "x64", "Cyberpunk2077.exe")
    saved_files = Params.get('cyberpunk', 'saved_files')

    # Order of what happens during setup up:
    # 1. Check if cyberpunk path is valid if not then fail test. 
    # 2. Check if cyberpunk exists in firewall rules, if not then add it
    # 3. Check if graphics setting is set, if so then apply it by uploading corresponding user settings file.
    # 4. Start Cyberpunk with -skipStartScreen and -fullscreen arguments.
    # 5. Clean up benchmark results folder so it can be populated with current runs results. 

    # Check if Cyberpunk executable exists using cmd.exe
    check_result = scenario._call(["cmd.exe", f'/C if exist "{cyberpunk_executable}" (echo EXISTS) else (echo NOT_FOUND)'], expected_exit_code="")
    
    if "NOT_FOUND" in check_result:
        logging.error(f"Cyberpunk executable not found at: {cyberpunk_executable}")
        raise Exception(f"Cyberpunk2077.exe not found at {cyberpunk_executable}, confirm that game has been installed. ")
   
    # Check if cyberpunk exists in firewall rules, if not then add it. 
    firewall_check = scenario._call(
        ["cmd.exe", '/C netsh.exe advfirewall firewall show rule name="Cyberpunk 2077"'],
        expected_exit_code=""
    )
    if "No rules match" in firewall_check:
        logging.debug("Cyberpunk 2077 firewall rule not found; adding it.")
        scenario._call(["cmd.exe", f"""/C netsh.exe advfirewall firewall add rule name="Cyberpunk 2077" program="{cyberpunk_executable}" dir=in action=allow enable=yes localport=any protocol=TCP profile=public,domain"""])
        scenario._call(["cmd.exe", f"""/C netsh.exe advfirewall firewall add rule name="Cyberpunk 2077" program="{cyberpunk_executable}" dir=in action=allow enable=yes localport=any protocol=UDP profile=public,domain"""])
    else:
        logging.debug("Cyberpunk 2077 firewall rule already exists; skipping add.")
    
    # Check if graphics setting is set.
    if graphics_settings:
        settings_map = {
            'med_1080':      'UserSettings_med_1080.json',
            'rt_ultra_1080': 'UserSettings_rt_ultra_1080.json',
            'rt_low_1440':   'UserSettings_rt_low_1440.json',
        }
        if graphics_settings in settings_map:
            settings_file = settings_map[graphics_settings]
            local_settings_file = os.path.join(
                os.path.dirname(__file__), "cyberpunk_settings_files", settings_file
            )
            user_setting_path = os.path.join(
                scenario.userprofile, "AppData", "Local", "CD Projekt Red", "Cyberpunk 2077"
            )

            # The settings folder is created on first launch of the game, not at
            # install time, so make sure it exists before uploading.
            scenario._call(
                ["cmd.exe", f'/C if not exist "{user_setting_path}" mkdir "{user_setting_path}"'],
                expected_exit_code=""
            )

            logging.info(f"Applying graphics preset '{graphics_settings}' to {user_setting_path}")
            scenario._upload(local_settings_file, user_setting_path)

            # The game reads "UserSettings.json"; rename the uploaded preset file
            # to that name (overwriting any existing UserSettings.json).
            uploaded_file = os.path.join(user_setting_path, settings_file)
            target_file = os.path.join(user_setting_path, "UserSettings.json")
            scenario._call(
                ["cmd.exe", f'/C move /Y "{uploaded_file}" "{target_file}"'],
                expected_exit_code=""
            )
        else:
            logging.info(f"Unknown graphics_settings value '{graphics_settings}'; skipping preset upload.")

    # Launch game
    scenario._call(["cmd.exe", f'/C "{cyberpunk_executable}" -skipStartScreen -fullscreen'], blocking=False)
    
    if int(benchmark_loops) > 0:
        # Subtract 1 from benchmark loops to account for 1st benchmark run is done outside replay loop. 
        Params.setOverride('cyberpunk', 'benchmark_loops', str(int(benchmark_loops)-1))
    
    # Determine correct benchmark path on the DUT. Ask the shell where the
    # Documents folder actually is — [Environment]::GetFolderPath('MyDocuments')
    # reads the registry value the shell uses, so it returns the OneDrive path
    # when Known Folder Move is enabled and the plain Documents path otherwise.
    documents_result = scenario._call(
        ["powershell.exe", "-Command \"[Environment]::GetFolderPath('MyDocuments')\""],
        expected_exit_code=""
    )
    documents_path = documents_result.strip().splitlines()[-1].strip() if documents_result else ""
    benchmark_path = os.path.join(
        documents_path, "CD Projekt Red", "Cyberpunk 2077", "benchmarkResults"
    ) if documents_path else ""

    # The benchmarkResults folder doesn't exist until the game has produced
    # results at least once. Verify before we try to clean it.
    benchmark_exists = "NOT_FOUND"
    if benchmark_path:
        benchmark_exists = scenario._call(
            ["cmd.exe", f'/C if exist "{benchmark_path}" (echo EXISTS) else (echo NOT_FOUND)'],
            expected_exit_code=""
        )

    if "EXISTS" not in benchmark_exists:
        # Could be 1st run and benchmark folder hasn't been created yet. Have it check if benchmark folder exists during teardown.
        Params.setCalculated('cyberpunk_benchmark_path', '')
        return

    logging.debug(f"Using benchmark path: {benchmark_path}")
    Params.setCalculated('cyberpunk_benchmark_path', benchmark_path)

    # Clean the benchmark folder so this run starts from an empty state.
    logging.info(f"Cleaning benchmark folder: {benchmark_path}")
    scenario._call(
        ["cmd.exe", f'/C del /q /s /f "{benchmark_path}\\*.*" & for /d %i in ("{benchmark_path}\\*") do rd /s /q "%i"'],
        expected_exit_code=""
    )

    # Check if any saved files exists, if so then set flag so correct key inputs can be sent.
    # Resolve %USERPROFILE% on the DUT (may not match the host's user).
    userprofile_result = scenario._call(
        ["cmd.exe", "/C echo %USERPROFILE%"],
        expected_exit_code=""
    )
    userprofile = userprofile_result.strip().splitlines()[-1].strip() if userprofile_result else ""

    if userprofile:
        saves_path = os.path.join(userprofile, "Saved Games", "CD Projekt Red", "Cyberpunk 2077")
        # /b = bare names only, /ad = directories only. findstr exits 0 if any dir name contains "save".
        dir_listing = scenario._call(
            ["cmd.exe", f'/C dir /b /ad "{saves_path}" 2>nul | findstr /i save'],
            expected_exit_code=""
        )
        if dir_listing:
            logging.info("Save directory found")
            Params.setOverride('cyberpunk', 'saved_files', '1')
    else:
        logging.info("Could not resolve %USERPROFILE% on DUT; skipping saved-file check.")