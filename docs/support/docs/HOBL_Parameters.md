# Parameters

This is a description of the parameters that can be set for HOBL runs, either in a profile or overridden on the command line.


The format consists of "sections", which refer to a particular scenario or tool, except "global" which has parameters that pertain to all.  The parameters below each section pertain to that section.  Parameters are specified on the command line as `<section>:<key>=<value>`.   Ex:
    `global:dut_ip=127.0.0.1`  
Values can contain spaces, but not commas or semi-colons.

## global
`msa_account` - Microsoft account associated with Device Under Test (DUT).  Example value: "tester@outlook.com"

`dut_name` - Name of DUT, as reported by "hostname" command.  The name of the DUT will be changed to the name you put here.  Make sure names do not include '-' or spaces.  If you want to keep the current DUT host name, this can be omitted.

`dut_ip` - IP address of the DUT.  Can be a name or refer directly to the dut_name parameter with "[dut_name]" if local network supports DNS sufficiently.

`dut_architecture` - Architecture of DUT, valid values are: x64 (default) or arm64.

`dut_password` - Password associated with the MSA Account.  This is only used by dut_setup to configure auto-logon.

`result_dir` - The directory to write results.  Typically, this should be changed for each study with a path that includes the name of the study.  To prevent the need to manually change this dir, variables can be specified in square brackets in the path.  Any global parameter can be
a path variable, as well as the following special ones: [OS_BUILD], [LKG].  Example value:  "c:\hobl_results\\[dut_name]\\[study_type]\\[LKG]".

`dut_wifi_name` - Wireless LAN name (SSID) to be used by DUT.  Dut_setup uses this to create the Wi-Fi profile and establish initial connection.
dut_wifi_name: 

`dut_wifi_password` - Wireless LAN password for above SSID, used to auto connect to Wi-Fi.

`study_type` - The type of the study you are performing.  For weekly HOBL runs we typically put "HOBL".  This is used to organize study results and reports.

`tools` - List any tools that should be run with each **power** scenario, in a space-separated list.  Available tools are in the "tools" directory.  This is the typical set: "auto_recharge video_record display_brightness run_report".  More information on tools can be found in the "Tools" section of the [HOBL Usage](./HOBL_Usage.md) document.

`prep_tools` - List any tools that should be run with each **prep** scenario, in a space-separated list.  This is the typical set: "screen_record".

`post_run_delay`

`trace`

`charge_on_call` - Specify the shell command to execute to engage charging of the device.  This is used by the "charge_on" and "recharge" scenarios, as well as the "auto_recharge" and "auto_charge" tools.  Requires some sort of automated charging mechanism such as an iBoot or IP Power Strip.

`charge_off_call` - Specify the shell command to execute to disengage charging of the device and run on battery.  This is used by the "charge_off" and "recharge" scenarios, as well as the "auto_recharge" and "auto_charge" tools. Requires some sort of automated charging mechanism such as an iBoot or IP Power Strip.

The following callbacks can be used to execute shell commands at specific events, to enable integration with external programs and equipment.  For each callback below, the path to the test results will automatically be added by the system call with a separating space.  This is an example value used in the Microsoft lab to start our DAQ capture: "python msft_skt_client.py -port 4770 DAQ_Start"

`callback_test_begin`

`callback_test_end`

`callback_data_ready`

`callback_test_fail`

## dut_setup

`target_path` - Where to write the dut_setup files.  Leave blank to be prompted.

## display_brightness

`nits_map` - Specifies the brightness percentage associated with each nits value, if running the "display_brightness" tool.  The default brightness is 150nits, while the "lvp" scenario overrides this to 100nits.  So a typical map value should look something like: "150nits:65% 100nits:52%".  Different devices have different brightness curves, so should be measured with luminance meter to determine the correct settings.

## audio_volume

`volume` - Specifies the volume level to be set before each run, if running the "audio_volume" tool.

## netflix
You need to have a Netflix account to run the Netflix scenario.  Provide username and password here.

`netflix_username`

`netflix_password`

## office_install

`activate` - Enter "0" to use the 5-day free trial, or "1" to activate a valid license associated with the MSA.

## run_report

`template` - Path to the Excel template for converting DAQ rails to subsystem summaries.

`script` - Path to the script to run to roll up DAQ data.  Each lab is responsible for developing a script for their unique DAQ systems.  But we are happy to help.  Leave blank for Rundown studies that don't use DAQ systems.

## study_report

`study_type` - Type of study to be put on the Config sheet.  Typically set to "[study_type]" to leverage the global parameter.

`product` - Name of product or program to be put on Config sheet.

`template` - The Excel template used to roll up the data.  Leave blank to use the standard HOBL template.  For Rundowns, "docs\\basic_study_report_template.xlsx" should be used.

`goals` - Path to CSV file of subsystem power goals.

`trend` - Path to top level of studies to generate trend data.

`adders` - Path to CSV file of keyboard/touch/trackpad adders.

`name` - Optionally specify a more detailed base name for the study report.

`battery_capacity` - Battery capacity in Wh.

`battery_derating` - Derating factor for the battery capacity.  i.e. 5% would be 0.05

`active_target` - Target in hours for Active On battery life.

`hobl_target` - Target in hours for HOBL.

`hibernate_budget_target` - If this much percentage of the battery is consumed in Standby in a 24h period, the system will go into Hibernate.

## power_light
This specifies which rails of onboard power meter chips to roll up for the following subsystems.

`soc` - Rails for SOC, separate rails with " | ". E.g. "PM_TOTAL_VCCIN_IN | PM_TOTAL_VCCIN_AUX_IN |  PM_TOTAL_3P3V_TOP_IN"

`wifi` - Rails for Wi-Fi.

`storage` - Rails for Storage.

`memory` - Rails for Memory.

`display` - Rails for Display.

`total` - Rail for total power.

`total_active` - Rail for total power in active (screen on).

`total_standby` - Rail for total power in standby.
