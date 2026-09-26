# HOBL Scenarios

## cinebench

The Cinebench benchmark.


<u>Parameters:</u>

`duration` - Minimum run time in seconds **Default:** `60` 

`workload` - Workload type: single_core or multi_core **Default:** `multi_core`  **Options:** `single_core, multi_core`

`installer_path` - Path to Cinebench installer on host machine. This should be the directory for your device architecture, containing the extracted Cinebench files, including cinebench.exe **Default:** `` 

## collect_logs

Collect various system logs.

## copilot

Nonfuctional.  Needs to be updated for new architecture.

## consumer_multitasker

Use the HOBL UI to run the `ConsumerMultitasker_v0.5` workload. The scenario name exposed in the UI is `consumer_multitasker`.

### Prerequisite: Enable diagnostic data

To enable PerfMetrics collection, turn on diagnostic data on the DUT:

1. Open PowerPoint.
2. Open the **File** tab.
3. Select **Account** in the lower-left section.
4. Select **Manage Settings**.
5. Check **Send Diagnostic Data**.
6. Select **OK**.
7. Close PowerPoint.

### Run the workload

1. Open the HOBL UI and create a new job.
2. Add the `consumer_multitasker` scenario and configure it as follows:

	| Setting | Value |
	| --- | --- |
	| Enabled | Yes |
	| Tools | `perf_utc` (performance data), `power_light` (power data), `run_report` (results rollup) |
	| Parameters | `enterprise_collab:perf_run=1`<br>`perf_utc:cm=1` |

3. Submit the job. The HOBL UI automatically adds and runs the required prep scenarios before the measured workload.

Results are written under the `result_dir` configured in the selected device profile. Each iteration produces:

* PerfMetrics in `consumer_multitasker_<iteration>_PerfMetrics.csv`.
* Power metrics in `consumer_multitasker_<iteration>_power_light_summary.csv`.

The `power_light` tool requires the DUT to have a supported Maxim chipset. If the DUT does not have a supported Maxim chipset, use the battery rundown method to measure power instead.
## iperf3

Runs iperf3 network throughput tests against a remote server while measuring power.

Supports four predefined test profiles (T1-T4) drawn from the iperf3 test matrix, plus
a 'custom' option that accepts any iperf3 argument string. Power/performance collection
is enabled so each run captures the power impact of the traffic pattern alongside the
raw throughput numbers.

The scenario blocks on iperf3's process exit (expected exit code 0). The duration
parameter feeds the -t flag in the command; it does not drive any internal timer.

Results written to the run directory:
    iperf3_output.txt  —  raw iperf3 console output (stdout + stderr)
    iperf3.csv         —  parsed key metrics (throughput, jitter, packet loss)


<u>Parameters:</u>

`server_ip` - IP address of the iperf3 server (required for T1-T4) **Default:** `` 

`test_type` - Test profile to run: T1, T2, T3, T4, or custom **Default:** `T1`  **Options:** `T1, T2, T3, T4, custom`

`custom_arguments` - Full iperf3 argument string when test_type='custom'. Include everything after 'iperf3', e.g. '-c 192.168.1.1 -u -b100M -t 60'. Ignored for T1-T4. **Default:** `` 

`duration` - Seconds passed to iperf3 via -t (T1-T4 only). Also used to size the call timeout safety net for custom tests. **Default:** `300` 

`wlan_logging` - Set to '1' to capture Wi-Fi layer telemetry alongside iperf3. Logs adapter error/discard counter deltas (Get-NetAdapterStatistics), a 5-second channel/RSSI/rate poll time series, and WLAN AutoConfig event log entries (connects, disconnects, roaming, channel switches). Adds wlan_*.txt / wlan_events.csv to the results directory and appends wlan_* metrics to iperf3.csv. **Default:** `0`  **Options:** `0, 1`

## lvp

Plays a video on full screen for a specified amount of time.  


<u>Parameters:</u>

`title` - The file name of the video **Default:** `ToS-4k-1920` 

`duration` - Time to play the video in seconds **Default:** `300` 

`airplane_mode` - Enable airplane mode during video playback **Default:** `0`  **Options:** `0, 1`

`radio_enable` - Enable or disable radio during video playback if airplane_mode parameter is set to 1 **Default:** `1`  **Options:** `0, 1`

## lvp_jeita

Plays a video in full screen mode in accordance with reqirements set by the Japan Electronics and Information Technology Industries Association for battery operated electronic devices being released in Japan.

Please do not alter parameters as they have been set to meet the requirements of that governing body


<u>Parameters:</u>

`title` - The file name of the video **Default:** `ToS-4k-1920` 

`duration` - Time to play the video in seconds **Default:** `300` 

`airplane_mode` - Enable airplane mode during video playback **Default:** `0`  **Options:** `0, 1`

`radio_enable` - Enable or disable radio during video playback if airplane_mode parameter is set to 1 **Default:** `1`  **Options:** `0, 1`

## mincp_all

Microsoft Teams video call with 9 bot participants.
Local camera and mic are on, other 9 participants are bots sending video and audio.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `1`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`web_workload` - Specific websites to run. **Default:** `amazongot amazonvacuum googleimagesapollo googleimageslondon googlesearchbelgium googlesearchsuperbowl instagram reddit theverge wikipedia youtubenasa youtubetos`  **Options:** `amazonbsg, amazongot, amazonvacuum, googleimagesapollo, googleimageslondon, googlesearchbelgium, googlesearchsuperbowl, instagram, reddit, theverge, wikipedia, youtubenasa, youtubetos`

`mincp_workloads` -  **Default:** `live_captions copilot_query semantic_search click_todo productivity studioeffect_blur`  **Options:** `live_captions, copilot_query, semantic_search, click_todo, studioeffect_blur, productivity`

`background_timers` -  **Default:** `1`  **Options:** `0, 1`

`background_teams` -  **Default:** `1`  **Options:** `0, 1`

`background_onedrive_copy` -  **Default:** `1`  **Options:** `0, 1`

`simple_office_launch` -  **Default:** `0`  **Options:** `1, 0`

`perf_run` -  **Default:** `0`  **Options:** `0, 1`

## net_prep_wifi

Set device routing table to prefer Wi-Fi connection between DUT and HOBL Host, to ensure that prep scenarios do not run over cellular.


<u>Parameters:</u>

`net_prep_enabled` -  **Default:** `1` 

`connection` -  **Default:** `Wi-Fi` 

## perf_stress

Install pyenv + Python + numpy/psutil on DUT for percentile_stress.py


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `1`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`web_workload` - Specific websites to run during stress workload. reddit must be included (Tab 1 with new_tab=0). **Default:** `reddit amazongot googleimagesapollo youtubetos`  **Options:** `amazonbsg, amazongot, amazonvacuum, googleimagesapollo, googleimageslondon, googlesearchbelgium, googlesearchsuperbowl, instagram, reddit, theverge, wikipedia, youtubenasa, youtubetos`

`background_teams` -  **Default:** `1`  **Options:** `0, 1`

`stress_run` - For perf metrics **Default:** `1`  **Options:** `0, 1`

`stress_cpu_target` - Target CPU load percentage for stress mode. **Default:** `25`  **Options:** `0, 25, 50, 65, 75, 85`

`background_onedrive_copy` -  **Default:** `1`  **Options:** `0, 1`

`simple_office_launch` -  **Default:** `1`  **Options:** `1, 0`

`shell_probes` -  **Default:** `1`  **Options:** `0, 1`

`sleep_resume_midrun` - This will actually sleep the DUT (pressing the power button) **Default:** `0`  **Options:** `0, 1`

`edge_close_relaunch` - 1 = mid-run kill msedge and relaunch with 12 foreground sites. Side effect: destroys background Edge tabs (no automatic restore). Default 0 keeps bg tabs alive for the entire run. **Default:** `0`  **Options:** `0, 1`

`perftrack_app_launch` -  **Default:** `1`  **Options:** `0, 1`

`provider` - WPRP file to use for perf_utc tracing. **Default:** `perf_utc.wprp`  **Options:** `abl_perf.wprp, full_th.wprp, full_th_wpp.wprp, general_cpi_collector.wprp, GTPLight_CustomMemHardFaults.wprp, multimedia.wprp, perf_utc.wprp, pmu.wprp, power.wprp, power_heavy.wprp, power_light.wprp, power_memory.wprp, productivity_perf.wprp, stack_walk.wprp, thermal_power_light.wprp, web_perf.wprp`

`bg_heavy_capture` - 1 = launch collect_5min_traces.ps1 in the background on the DUT alongside the core trace. Uses a named WPR instance (perfStressHeavy). Saves rolling ETLs to C:\hobl_bin\perf_stress_heavy\<RunName>\WPR_<timestamp>.etl. WARNING: dual-session WPR perturbs metrics - debug use only. **Default:** `0`  **Options:** `0, 1`

`bg_heavy_capture_interval` - Rolling ETL segment length in minutes for bg_heavy_capture (default 5). A 15-20 min run at 5 min should produce ~3 segments; shorten if wpr -stop flush eats into the next interval. **Default:** `5`  **Options:** `3, 4, 5, 6`

`bg_edge_tabs` - 1 = open background Edge tabs to increase memory pressure and CPU stress. **Default:** `1`  **Options:** `0, 1`

`bg_edge_tab_loops` - Iterations of the web_bg_tabs site loop. Each iteration opens 5 background Edge tabs. Default 6 = 30 background tabs **Default:** `6`  **Options:** `1, 2, 3, 4, 5, 6, 8, 10`

## process_idle_tasks

Preforms various tasks that prepare a device for testing.  This includes queuing background maintenance tasks in Windows so they will not be running during tests.  To ensure consistent results, please run this scenario at least once per day on devices before starting tests.


<u>Parameters:</u>

`timeout` - Maximum time in seconds the automation will wait for tasks to complete **Default:** `1800` 

`loops` - Number of times the automation will attempt to perform tasks **Default:** `3` 

`run_idle_tasks` - Queues Windows idle tasks so they will not be running during tests **Default:** `1`  **Options:** `0, 1`

`final_reboot` - Sets if the device will reboot at the conclusion of process_idle_tasks **Default:** `1`  **Options:** `0, 1`

## standby

Puts the device into standby mode, still conneccted to the network.


<u>Parameters:</u>

`cs_duration` -  **Default:** `1200` 

`button_to_record_delay` -  **Default:** `900` 

`button_sleep_callback` -  **Default:** `` 

`button_wake_callback` -  **Default:** `` 

`local_button` -  **Default:** `1` 

`sleep_mode` -  **Default:** `` 

`connection` - Connected or Disconnected from the network during standby **Default:** `Connected`  **Options:** `Disconnected, Connected`

## system_prep

Performs various tasks that prepare a device for testing.


<u>Parameters:</u>

`hibernate_enabled` - Enables or disables hibernation on the device **Default:** `1`  **Options:** `0, 1`

`telemetry_enabled` - Enables or disables the gathering of optional diagnostic data in the OS **Default:** `0`  **Options:** `0, 1`

`theme` - Change the Windows theme **Default:** `current`  **Options:** `current, light, dark`

`wallpaper` - Sets the device's background image.  Uses image files stored in the %SYSTEMDRIVE%\hobl_bin\DesktopImages folder **Default:** `ColorChecker3000x2000.png` 

`final_reboot` - Sets if the device will reboot at the conclusion of daily_prep **Default:** `1`  **Options:** `0, 1`

`bpm_pcc_blm_disable` - Disable BPM, PCC, and BLM **Default:** `0`  **Options:** `0, 1`

## teams2_10p_aud_dtop

Microsoft Teams audio call with 9 bot participants.
Local camera is off and mic is on, other 9 participants are bots sending audio.
Local user is sharing desktop.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `9`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `0`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `0`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `1`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `300`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_1on1_audio

Microsoft Teams audio call with 1 bot participant.
Local camera is off and mic is on, other participant is a bot sending audio.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `1`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `0`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `0`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `300`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_1on1_video

Microsoft Teams video call with 1 bot participant.
Local camera and mic are on, other participant is a bot sending video and audio.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `1`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `300`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_3x3_audio

Microsoft Teams audio call with 9 bot participants.
Local camera is off and mic is on, other 9 participants are bots sending audio.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `9`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `0`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `0`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_3x3_present

Microsoft Teams video call with 9 bot participants.
Local camera and mic are on, other 9 participants are bots sending video and audio.
Local users is sharing screen.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `9`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_3x3_video

Microsoft Teams video call with 9 bot participants.
Local camera and mic are on, other 9 participants are bots sending video and audio.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `9`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_3x3_vid_share

Microsoft Teams video call with 9 bot participants.
Local camera and mic are on, other 9 participants are bots sending video and audio.
One of the bots is sharing a video.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `9`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_5p_rpres

Microsoft Teams video call with 4 bot participants.
Local camera and mic are on, other 4 participants are bots sending video and audio.
One of the bots is sharing a video.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `4`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `1`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `1`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `0`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `600`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_audio_desktop

Microsoft Teams audio call with 1 bot participant.
Local camera is off and mic is on, other participant is a bot sending audio.
Local user is sharing desktop.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is teams:duration + 30 min. **Default:** `0` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `1`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `0`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `0`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `\teams_resources\ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `1`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`duration` - The time in seconds to call for. Default is 600s or 5min. **Default:** `300`  **Options:** `60, 120, 300, 600`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `1`  **Options:** `0, 1`

## teams2_idle

Teams is launched and then minimized to run in the background for the duration of the test.


<u>Parameters:</u>

`duration` -  **Default:** `300` 

`minimize_all` -  **Default:** `1` 

`minimize_teams_only` -  **Default:** `0` 

## youtube

Plays a YouTube video in a web browser in Default View mode.

Steps:

1. Navigate to Tears of Steel YouTube video URL: [youtu.be/41hv2tW5Lc4](https://youtu.be/41hv2tW5Lc4)
2. Change video quality to 1080p.
3. Let video play for specified duration and loops.
4. Close web browser.


<u>Parameters:</u>

`duration` - Total scenario duration **Default:** `600` 

`loop_duration` - YouTube video playback duration before looping (max 480s) **Default:** `300` 

`full_screen` - Full Screen mode **Default:** `0`  **Options:** `0, 1`

## brightness_study_report

Extract brightness value from a path containing a Brightness-XX folder.


<u>Parameters:</u>

`result_path` -  **Default:** `` 

`name` -  **Default:** `` 

`device_name` -  **Default:** `` 

`backlight_key` - Metric name for backlight power in brightness curve report. **Default:** `DisplayLight Power (W)` 

`analog_key` - Metric name for analog/panel power in brightness curve report. **Default:** `DisplayLogic Power (W)` 

## comm_check

Checks for valid communications between host and DUT.

Steps:

1. Ping DUT
2. SimpleRemote RPC call
3. SimpleRemote Async call
4. WinAppDriver launch and communication
5. Report results

## mac_cinebench

Scenario to run Cinebench on Mac, supporting singleCore and multiCore runs, collecting scores and battery rundown.


<u>Parameters:</u>

`duration` - Minimum run time in seconds **Default:** `60` 

`workload` - Workload type: single_core or multi_core **Default:** `multi_core`  **Options:** `single_core, multi_core`

## mac_teams2_10p_aud_dtop

Microsoft Teams audio call with 9 bot participants.
Local camera is off and mic is on, other 9 participants are bots sending audio.
Local user is sharing desktop.


<u>Parameters:</u>

`meeting_time` - Set the time in minutes that the meeting can last up to. Default is 120min. **Default:** `120` 

`access_key` - The access key for the Teams Bots Server. Contact HOBL Support to inquire for a key. **Default:** `-1` 

`number_of_bots` - Sets the number of bots to have in the meeting. **Default:** `8`  **Options:** `1, 2, 4, 8, 9`

`bots_send_video` - Set to 1 if bots should have their cameras on. Set to 0 for audio only calls. **Default:** `0`  **Options:** `0, 1`

`bots_send_audio` - Set to 1 to have bots send audio. Set to 0 to have bots be muted. **Default:** `1`  **Options:** `0, 1`

`bots_share_screen` - Set to 1 to have the primary bot share its screen in the meeting. **Default:** `0`  **Options:** `0, 1`

`bots_test_server` - For advanced use. Set to 1 to use the testing instance of the bots server. Not Recomended for general use. **Default:** `0`  **Options:** `0, 1`

`duration` - Sets the time in seconds for the test to run. **Default:** `300`  **Options:** `60, 120, 240, 300, 600, 900`

`send_video` - Set to 1 to have the DUT turn on its camera. Set to 0 to have the DUT camera off. **Default:** `0`  **Options:** `0, 1`

`send_audio` - Set to 1 to have the DUT have its mic on. Set to 0 to have the DUT be muted. **Default:** `1`  **Options:** `0, 1`

`send_screen` - Set to 1 to have the DUT share its screen in the meeting. **Default:** `1`  **Options:** `0, 1`

`presentation_video_path` - Sets the path to the video file to use as the presented screen when the DUT is screen sharing. **Default:** `/teams_resources/ppt.mp4` 

`show_desktop` - Set to 1 to have the DUT screen share their desktop when screen sharing. Set to 0 to share a video of a presentation instead. **Default:** `1`  **Options:** `0, 1`

`bots_force_subscribe_resolution` - Force the bots to subscribe to a specific video resolution **Default:** `0`  **Options:** `0, 1080, 720, 480, 360`

`parse_MSTeams_Logs` - Set to 1 to parse Teams logs after collecting them. **Default:** `1`  **Options:** `0, 1`

`parser_location` - Sets the path to the parser to use to decode Teams logs. **Default:** `..\ScenarioAssets\Teamsdecode\bin\UnifiedLogging` 

`collect_call_health` - Set to 1 to have the call health data collected. **Default:** `1`  **Options:** `0, 1`

`collect_MSTeams_Logs` - Set to 1 to collect MS Teams logs of the meeting after exiting the meeting. **Default:** `1`  **Options:** `0, 1`

`maintain_bots` - Set to 1 to have the test peridically check that all bots are present in the call and add bots if needed. **Default:** `0`  **Options:** `0, 1`

