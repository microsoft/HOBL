# HOBL Scenarios

## cinebench

The Cinebench benchmark.


<u>Parameters:</u>

`duration` - Minimum run time in seconds **Default:** `60` 

`workload` - Workload type: single_core or multi_core **Default:** `multi_core`  **Options:** `single_core, multi_core`

## collect_logs

Collect various system logs.

## copilot

Nonfuctional.  Needs to be updated for new architecture.

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

## process_idle_tasks

Preforms various tasks that prepare a device for testing.  This includes queuing background maintenance tasks in Windows so they will not be running during tests.  To ensure consistent results, please run this scenario at least once per day on devices before starting tests.


<u>Parameters:</u>

`timeout` - Maximum time in seconds the automation will wait for tasks to complete **Default:** `1800` 

`loops` - Number of times the automation will attempt to perform tasks **Default:** `3` 

`run_idle_tasks` - Queues Windows idle tasks so they will not be running during tests **Default:** `1`  **Options:** `0, 1`

`final_reboot` - Sets if the device will reboot at the conclusion of process_idle_tasks **Default:** `1`  **Options:** `0, 1`

## system_prep

Preforms various tasks that prepare a device for testing.


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

## youtube25

Plays a YouTube video in a web browser in Default View mode.

Steps:

1. Navigate to Tears of Steel YouTube video URL: [youtu.be/41hv2tW5Lc4](https://youtu.be/41hv2tW5Lc4)
2. Change video quality to 1080p.
3. Let video play for specified duration and loops.
4. Close web browser.


<u>Parameters:</u>

`duration` -  **Default:** `600` 

`loops` -  **Default:** `1` 

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

