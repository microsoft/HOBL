# HOBL Tools

## audio_volume

Set specified audio volume.


<u>Parameters:</u>

`volume` -  **Default:** `Unknown` 

## auto_charge

Turn off charger before scenario, turn it on after.


<u>Parameters:</u>

`delay` -  **Default:** `5` 

`mode` -  **Default:** `DC` 

## auto_recharge

Pause run and recharge device when battery drops below [charge_threshold], then resume.


<u>Parameters:</u>

`charge_threshold` -  **Default:** `40` 

`resume_threshold` -  **Default:** `95` 

`charge_on_call` -  **Default:** `` 

`charge_off_call` -  **Default:** `` 

## battery_bar

Overlays a widget showing battery level.


<u>Parameters:</u>

`version` -  **Default:** `v1.0.0` 

## battery_stats

Deprecated.

## bat_logger

Surface only.  Logs battery details over time.

## collect_logs

Collect various system logs in the case of scenario failure.

## custom_trace

Periodically start ETL traces.


<u>Parameters:</u>

`providers` - ETL provider files to use **Default:** `power_light.wprp`  **Options:** `abl_perf.wprp, full_th.wprp, full_th_wpp.wprp, general_cpi_collector.wprp, multimedia.wprp, perf_utc.wprp, pmu.wprp, power.wprp, power_heavy.wprp, power_light.wprp, power_memory.wprp, productivity_perf.wprp, stack_walk.wprp, thermal_power_light.wprp, web_perf.wprp`

`trace_duration` - The duration of the trace in seconds **Default:** `300` 

`start_delay` - The start delay before the trace starts in seconds **Default:** `0` 

`enable_check` - Check the result of the trace. 0 = no check, 1 = check **Default:** `1`  **Options:** `0, 1`

`single_run` - Run the trace only once. 0 = no, 1 = yes **Default:** `0`  **Options:** `0, 1`

## debug_logs

Deprecated.


<u>Parameters:</u>

`bugreport` -  **Default:** `1` 

`appVersion` -  **Default:** `0` 

## detect_devices

Deprecated.

## display

Combined display settings tool. Configures one or more display properties
before a test. Initial values are saved to the DUT registry on first use
and only restored when display_restore=1 is set.

Only parameters that are explicitly provided are processed — empty parameters
are ignored, so the tool can be called for any subset of operations.

Parameters:
  als_adaptive_brightness       0/1 — adaptive brightness (ALS) on/off (Windows only)
  hdr                           0/1 — HDR on/off (Windows only)
  hdr_auto                      0/1 — Auto HDR on/off (Windows only)
  refresh_rate                  60/120/dynamic — display refresh rate (Windows only)
  content_adaptive_brightness   Off/Always/On battery only — CABC mode (Windows only)
  adaptive_color                0/1 — adaptive color management on/off (Windows only)
  brightness                    brightness value (e.g. 65, 65%, 150nits)
  nits_map                      nits-to-slider mapping (e.g. "100nits:50% 150nits:65%")
  display_restore               1 — restore all saved initial values after test


<u>Parameters:</u>

`als_adaptive_brightness` - Adaptive brightness (1=on, 0=off). **Default:** ``  **Options:** `0, 1`

`adaptive_color` - Adaptive color (1=on, 0=off). **Default:** ``  **Options:** `0, 1`

`content_adaptive_brightness` - CABC: Off, Always, or OnBatteryOnly. **Default:** ``  **Options:** `Off, Always, OnBatteryOnly`

`hdr` - HDR (1=on, 0=off). **Default:** ``  **Options:** `0, 1`

`hdr_auto` - Auto HDR (1=on, 0=off). **Default:** ``  **Options:** `0, 1`

`refresh_rate` - Refresh rate: 60, 120, or dynamic. **Default:** ``  **Options:** `60, 120, dynamic`

`brightness` - Brightness slider percentage or desired nits (e.g. 65, 65%, 150nits).  If you specify nits, the nits_map parameter will be used to determine the corresponding slider value. **Default:** `150nits` 

`nits_map` - Nits-to-slider mapping.  Use luminance meter to determine for specific device. **Default:** `100nits:50% 150nits:65%` 

`display_restore` - Restore all display settings to saved initial values (1=restore). **Default:** ``  **Options:** `0, 1`

## display_brightness

Map display brightness slider percentage to nits value specified by scenarios.


<u>Parameters:</u>

`brightness` -  **Default:** `150nits` 

`nits_map` -  **Default:** `100nits:50% 150nits:65%` 

## dumpcap

Dump Wireshark capture.


<u>Parameters:</u>

`interface` -  **Default:** `Wi-Fi` 

## etl_trace

Collect ETL trace from specified [providers].


<u>Parameters:</u>

`providers` - ETL provider files to use **Default:** ``  **Options:** `abl_perf.wprp, full_th.wprp, full_th_wpp.wprp, general_cpi_collector.wprp, multimedia.wprp, perf_utc.wprp, pmu.wprp, power.wprp, power_heavy.wprp, power_light.wprp, power_memory.wprp, productivity_perf.wprp, stack_walk.wprp, thermal_power_light.wprp, web_perf.wprp`

## frame_data

Collect and parse framerate and timing data.  Does not have a significant impact on power consumption.

## kill_teams

Kill all instances of Teams processes.


<u>Parameters:</u>

`restart` -  **Default:** `0` 

## kill_widgets

Stops the Windows Widgets from running.

## media_perf

Deprecated.


<u>Parameters:</u>

`autoxa_path` -  **Default:** `C:\"Media eXperience Analyzer\AutoXA.exe"` 

## mep_toggle

Enable/disable specified MEP features.


<u>Parameters:</u>

`framing` -  **Default:** `0` 

`eye_gaze` -  **Default:** `0` 

`blur` -  **Default:** `0` 

`portraitlight` -  **Default:** `0` 

`creative` -  **Default:** `0` 

`standardframing` -  **Default:** `0` 

`cinematicframing` -  **Default:** `0` 

`portraitblur` -  **Default:** `0` 

`standardblur` -  **Default:** `0` 

`standardeye` -  **Default:** `0` 

`enhancedeye` -  **Default:** `0` 

`illustrated` -  **Default:** `0` 

`animated` -  **Default:** `0` 

`watercolor` -  **Default:** `0` 

## netsh

Get ETL trace of wns_client.

## network_ping

Deprecated.


<u>Parameters:</u>

`dut_ip` -  **Default:** `` 

## net_speed_test

Run speedtest.exe to gauge internet bandwidth.

## net_stat

Reports number of bytes transferred over Wi-Fi vs Cellular.

## perf

Calculates a MOS score from an abl_perf run.


<u>Parameters:</u>

`provider` -  **Default:** `abl_perf.wprp` 

## perfmon_util

Trace specified performance counters that report utilization.


<u>Parameters:</u>

`processor_counter` - Processor counter to use **Default:** `\Processor(_Total)\% Processor Time` 

`memory_counter` - Memory counter to use **Default:** `\Memory\Available Bytes` 

`gpu_counter` - GPU counter to use (per process, per instance) **Default:** `\GPU Engine(*engtype_3D)\Utilization Percentage` 

`npu_counter` - NPU counter to use (per process, per instance) **Default:** `\GPU Engine(*engtype_Compute)\Utilization Percentage` 

## perf_screen_capture

A template that can be used for creating new tools.

## perf_utc

Collects and processes UTC Perftrack scenarios


<u>Parameters:</u>

`provider` - WPRP file to use for UTC Perftrack traces. **Default:** `perf_utc.wprp`  **Options:** `abl_perf.wprp, full_th.wprp, full_th_wpp.wprp, general_cpi_collector.wprp, multimedia.wprp, perf_utc.wprp, pmu.wprp, power.wprp, power_heavy.wprp, power_light.wprp, power_memory.wprp, productivity_perf.wprp, stack_walk.wprp, thermal_power_light.wprp, web_perf.wprp`

## phm

Run Intel's Power House Mountain tool.


<u>Parameters:</u>

`node` -  **Default:** `C:\Program Files\nodejs\node.exe` 

`phm_args` -  **Default:** `!cpup` 

`phm_base_path` -  **Default:** `C:\Program Files\PowerhouseMountain\` 

`phm_server` -  **Default:** `app.js` 

`phm_trace` -  **Default:** `phm-client.js` 

`phm_dut_trace_path` -  **Default:** `C:\Program Files\PowerhouseMountain\traces` 

## pktmon_count

Count types of network packets transmitted and received.


<u>Parameters:</u>

`comp` -  **Default:** `` 

## pktmon_log

Use pktmon to log network traffic.


<u>Parameters:</u>

`comp` -  **Default:** `` 

## postures_screen_rotation

Deprecated.


<u>Parameters:</u>

`posture_code` -  **Default:** `5` 

## powercfg

Collect sleep study and battery reports.


<u>Parameters:</u>

`battery_report` -  **Default:** `1` 

## power_heavy

Collect and parse a detailed power trace.  Has a significant impact on power consumption.


<u>Parameters:</u>

`soc` -  **Default:** `` 

`wifi` -  **Default:** `` 

`memory` -  **Default:** `` 

`display` -  **Default:** `` 

`storage` -  **Default:** `` 

`total` -  **Default:** `` 

`total_active` -  **Default:** `` 

`total_standby` -  **Default:** `` 

## power_light

Collect and parse a lightweight power trace.  Does not have a significant impact on power consumption.


<u>Parameters:</u>

`soc` -  **Default:** `` 

`wifi` -  **Default:** `` 

`cellular` -  **Default:** `` 

`memory` -  **Default:** `` 

`backlight` -  **Default:** `` 

`display` -  **Default:** `` 

`storage` -  **Default:** `` 

`sam` -  **Default:** `` 

`blade` -  **Default:** `` 

`retimers` -  **Default:** `` 

`total` -  **Default:** `` 

`total_active` -  **Default:** `` 

`total_standby` -  **Default:** `` 

`provider` - WPRP file to use for power light traces. **Default:** `power_light.wprp`  **Options:** `power_light.wprp, thermal_power_light.wprp`

## power_mode

Switch to specified power mode (best power efficiency, recommended/balanced, better, best/best performance). Returns to last mode on test end.


<u>Parameters:</u>

`mode` - The power mode to switch to (best power efficiency, recommended/balanced, better, best performance). **Default:** `best power efficiency`  **Options:** `best power efficiency, recommended/balanced, better, best performance`

## random_fail

Randomly fail a test, for devolpment/debug purposes.

## run_report

Generate a report for the test run.


<u>Parameters:</u>

`script` -  **Default:** `` 

`goals` -  **Default:** `` 

`template` -  **Default:** `` 

`report_level` -  **Default:** `2` 

`result_path` -  **Default:** `` 

`phase_power_type` -  **Default:** `Total` 

`fail_on` -  **Default:** `` 

`files` -  **Default:** `run_info.csv study_vars.csv rundown.csv *power_data.csv maxim_summary*.csv *power_light_summary.csv *e3_power_summary.csv *ConfigPre.csv *ConfigPost.csv *top_processes.csv *socwatch.csv *.csv` 

`name_prefix` -  **Default:** `` 

## screenshot

Record periodic screen shots, for debug purposes.


<u>Parameters:</u>

`pause` -  **Default:** `0` 

## screen_record

Records a screen cast from the DUT for debug purposes.  Has considerable power impact.

## serialize_copyback

Deprecated.


<u>Parameters:</u>

`counter` -  **Default:** `900` 

`lock_path` -  **Default:** `` 

## socwatch

Run Intel's SOCWatch tool.


<u>Parameters:</u>

`delay` -  **Default:** `0` 

`additional_args` -  **Default:** `-f cpu-pkgc-dbg -f pcie -f platform-ltr -f panel-srr -f cpu-cstate -f cpu-pstate -f gfx-cstate -f gfx-pstate -f acpi-dstate -f sstate -f ddr-bw -f timer-resolution -f cpu-gpu-concurrency -f pch-slps0 -f pcie-lpm -f hw-gfx-pstate -f ddr-bw -f pch-ip-active-all -f pch-ip-status -f sys -f sa-freq -f pch-all` 

## stress_utc

Collects and processes UTC Perftrack scenarios for stress workloads.
Outputs a CSV with PT number instead of Scenario name.


<u>Parameters:</u>

`provider` - WPRP file to use for UTC Perftrack traces. **Default:** `perf_utc.wprp`  **Options:** `abl_perf.wprp, full_th.wprp, full_th_wpp.wprp, general_cpi_collector.wprp, multimedia.wprp, perf_utc.wprp, pmu.wprp, power.wprp, power_heavy.wprp, power_light.wprp, power_memory.wprp, productivity_perf.wprp, stack_walk.wprp, thermal_power_light.wprp, web_perf.wprp`

## study_report

Generate a report for the study (all runs in the same study directory).


<u>Parameters:</u>

`result_path` -  **Default:** `` 

`template` -  **Default:** `docs\hobl_study_report_template.xlsx` 

`weights` -  **Default:** `` 

`trend` -  **Default:** `` 

`goals` -  **Default:** `` 

`adders` -  **Default:** `` 

`name` -  **Default:** `` 

`active_target` -  **Default:** `` 

`hobl_target` -  **Default:** `` 

`battery_capacity` -  **Default:** `` 

`battery_min_capacity` -  **Default:** `` 

`battery_derating` -  **Default:** `` 

`battery_reserve` -  **Default:** `` 

`os_shutdown_reserve` -  **Default:** `` 

`hibernate_timeout` -  **Default:** `` 

`hibernate_budget_target` -  **Default:** `` 

`device_name` -  **Default:** `` 

`comments` -  **Default:** `` 

`csv_path` -  **Default:** `` 

`enable_phase_report` -  **Default:** `1` 

`uploader` -  **Default:** `` 

## surface_logger

Surface-only.  Run SurfaceLogger tool for debug.


<u>Parameters:</u>

`start_args` -  **Default:** `-Start SSHLogs -Method Tracelog -Drivers SurfaceSerialHubDriver` 

`stop_args` -  **Default:** `-Stop SSHLogs -Method Tracelog` 

## system_deck

AMD-only.

## tearcheck

Check stdin for 'teardown' and end test when consumed

## thermal_daq

A tool for reading thermocouple data from a thermal DAQ server.


<u>Parameters:</u>

`thermal_daq_host` -  **Default:** `127.0.0.1` 

`thermal_daq_port` -  **Default:** `5000` 

`polling_interval` -  **Default:** `5` 

`channels` -  **Default:** `None` 

## timeout_wake

Deprecated. Wake the DUT on timeout.

## tool_template

A template that can be used for creating new tools.


<u>Parameters:</u>

`example_parameter` -  **Default:** `example value` 

## touch_activation

Surface-only.  Digitizer debug.


<u>Parameters:</u>

`single_touch_time` -  **Default:** `0` 

`multi_touch_time` -  **Default:** `48` 

`pen_track_time` -  **Default:** `0` 

`idle_time` -  **Default:** `12` 

`sid` -  **Default:** `3` 

`control_list` -  **Default:** `` 

`start_delay` -  **Default:** `0` 

`timer` -  **Default:** `` 

## ttd

Run TTD (Time Travel Debugging)


<u>Parameters:</u>

`start` - Start time during test execution in seconds. **Default:** `0` 

`end` - End time during test execution in seconds. **Default:** `0` 

`process` - Process to attach to. **Default:** `` 

## video_record

Record a video of the scenario using a camera attached to the Host USB, or an RTSP stream.


<u>Parameters:</u>

`camera_num` -  **Default:** `0` 

`rtsp_url` -  **Default:** `` 

`camera_name` -  **Default:** `` 

`fps` -  **Default:** `5` 

`xres` -  **Default:** `1920` 

`yres` -  **Default:** `1080` 

`quality` -  **Default:** `25` 

`rotation` -  **Default:** `0` 

`show` -  **Default:** `0` 

