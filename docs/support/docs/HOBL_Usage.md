# Usage

The test scenarios that make up the "HOBL" suite have been pre-assembled in a "test plan", `testplans\hobl.ps1`.
* Test plans can be run from the command line, if integrating with higher level automation, but running from the HOBL UI has a lot of benefits and is preferred.
* Controlling which scenarios to run, such if doing re-runs of select scenarios, can be done by either commenting out lines in the test plan, or utilizing the checkboxes in the GUI interface.

## Top level
  * The HOBL framework is a general purpose test framework based on the Python UnitTest framework.  Windows Application Driver and image recognition technologies are used to remotely control the interaction of applications and web sites.
  * hobl.cmd is the top-level file that can be executed from the command line.  Give arguments for the profile and the scenario to be run.  For example, to run the web scenario:
```
    hobl.cmd -p my_profile.ini -s web
```
 * However, this command is very limited and not supported for external use.  The HOBL UI is a much better way to run tests and plans.  For interfacing with external systems, ask HOBLsupport about the available REST API.

## Scenarios
* The hobl/scenarios/[os] dir contains the scenarios that can be run.  Some scenarios are actual test cases, some do supporting tasks (such as turning the charger on/off), while others are just to prepare the device (such as installing office).  The scenarios that make up the "hobl" test plan are the best maintained.  Other scenarios may or may not still be maintained.
* A scenario, or test case, contains the code to interact with the DUT (Device Under Test) according to a specific user scenario.
* Most scenarios require some initial preparation.  A special "prep" scenario can determine what additional preparation scenarios are need for a specified test scenario, and will automatically execute them.  Note that the HOBL UI will do this automatically for you.  But for command-line execution, to prepare for the "web" scenario, for example, the "prep" scenario can be run like this:
```
    hobl.cmd -p my_profile.ini -s prep prep:scenarios_to_prep=web
```
* Descriptions of available scenarios can be seen here: [Scenarios](HOBL_Scenarios.md)

## Parameters
There are 3 levels of parameters:
* Default values of scenario-specific parameters are set in each scenario itself.  Generally, the default values are set to what should be used for a proper HOBL run.  The top-level hobl.py sets the "global" default parameters, which are those common to all scenarios.
* A Device Profile can be used to override the defaults.  The can be created from the "Device Profiles" menu in the HOBL UI.  It ultimately get saved as a .ini file in c:\profiles, so command-line operations can point to it there.  The file has sections for "global", as well as any relevant scenarios.  A "default.ini" is provided as a starting point, which contains the parameters that would typically need to be overwritten, such as the various credentials needed.  Users should copy this to create their own.  It is expected that a lab would have a separate Device Profile file for each DUT, as each DUT would need its own accounts.
* Finally, parameters can be overridden on the command line.  This overrides both the defaults and the Device Profile file.  The argument format is:
  ```
      <scenario>:<key>=<value>
  ```
* Descriptions of available parameters can be seen here: [Parameters](HOBL_Parameters.md)

## Tools
* Two of the global parameters is "tools" and "prep_tools".  These are distinct because there is generally a separate set of tools we run for measured test scenarios (such as ETL tracing) vs prep scenarios (such as screen_record).
* In your profile, you can specify a space-separated default list of tools from the tools folder to run for every scenario of each type.
* Tools can also be easily overridden per scenario when creating a new job in the HOBL UI, by clicking in the "tools" column and choosing from the drop-down.  The parameter will be populated appropriately behind the scenes.
* A tool is a python file that contains specific predefined methods called at specific phases of the test flow.  This can be used to control things like settings, tracing, measurements, or external equipment by sending specific commands at the appropriate time.
* Create a new tool by copy/rename/editing an existing one that is most similar.
* Tools can be added to an existing list on the command line, using a "+" symbol as the first character.  i.e.
    * hobl.cmd -p my\_params.ini -s lvp global:tools="+video_record"
    * This will add "video\_record" to the list of tools specified in my_params.ini
* Common tools include:
    * auto_recharge - Turns on the charger when battery level reaches a specified low threshold, and turns off at the specified upper threshold.
    * auto_charge - Turns off the charger before each scenario and turns on after.
    * etl_trace - Records ETL traces using WPR.  Specify .wprp providers on the "providers" parameter.
    * power_light - Lightweight tracing that doesn't significantly impact power consumption.  Traces and summarizes running process and the estimated power they consume.  Critical for determining variability in runs.
    * power_heavy - Exhaustive collection and reporting of power-related activities in the system, but does have a significant impact on power itself.
    * powercfg - Runs the Windows powercfg.exe command for such things as a Sleep Study Report.
    * run\_report - Rollup a report of each run.  This is needed for the study_report scenario to rollup a report of the whole study.
    * screenshot - Capture screenshots of the DUT at a specified interval.
    * video_record - Record video of a scenario from a camera connected to the host.
    * screen_record - Record video of a scenario from capturing the display buffer on the DUT itself.  This consumes a lot of power and should only be done on scenarios where Power consumption is not being studied.  However, it gives very clear video for debug purposes without requiring an external camera.
* Descriptions of available tools can be seen here: [Parameters](HOBL_Parameters.md)

## DUT folders
* There are 2 folders created on the DUT:  
    * On Windows:  c:\hobl_bin and c:\hobl_data
    * On macOS:  /users/Shared/hobl_bin and /users/Shared/hobl_data
* hobl_bin is where any scripts, executables, or resources that are needed for execution are copied, usually by a prep scenario.
* hobl_data is cleared at the beginning of each scenario.  Any data produced by the scenario and tools while running on the DUT gets put there.  At the end of the scenario everything in that folder is copied back to the host computer's result directory.  Examples, include ETL traces, log files, config_check output, etc.

## Result directory
* The global parameter "result_dir" represents the base directory on the host where results will be stored.  Default is "c:\hobl_results".  Relative paths must not be used.
* There is also a "study_type" parameter that will automatically get appended to the result_dir.  It's optional, but is recommended for organizing test results for different studies.  This can be set in the profile, but there is also a convenient field at the top of the New Job page for overriding it.
* For more advanced study organization, the New Job page allows use to specify Study Variables.  These are ideal for managing the variables in experiments.  The UI will automatically generate runs for all combinations of specified study variables and their values.  The variable names and values will be appended to the result directory for data organization, and will also be recorded in the result metadata to facilitate database filtering and querying.
* The global parameter "run_type" allows for an additional subdirectory to be specified.  Default is "Prep" for all prep scenarios and "Power" for measured test scenarios.  This allows reporting tools to know which scenarios to try and roll up.
* Finally, the leaf directory automatically created is of the form `<scenario>_<iter>`.  Where `<iter>` is a 3-digit number that auto increments for each run.
* So the final result directory is `<result_dir>\<study_type>\<studyvar1-val1>\<studyvar2-val1><run_type>\<scenario>_<iter>`

## Reporting
* Run Report - A report rolled up for each scenario run. To run, add "run_report" to the list of tools on your global:tools parameter.  This does two things:
    1. The tool runs an optional script specified in the script_path parameter to roll up any data collected by external equipment, such as DAQs, to a *_power_data.csv file, that just contains rows of `<key>,<val>` for any metrics you would like rolled up.  Since such a script is particular to individual lab environments, it is not provided, but we can help with creation of yours.
    2. A rollup_metrics script is run that rolls up all available .csv files, such as from other tools that may have been run, as well as the pre and post config_check runs, into a single *_metrics.csv file.  This summary file will be used by the study_report rollup.  The rollup_metrics.py script is in the "utilities" folder and can also be run manually and recursively on a full set of runs in one shot.
* Study Report - Rolls up the Run Reports for an entire study.
    * Study Report is run as a scenario when you want to rollup existing results.
        * hobl.cmd -p my_params.ini -s study_report
    * There are a number of optional parameters to direct the output:
        1. result_path - study directory to roll up, defaults to result_dir specified in the profile.
        1. template - A spreadsheet to be used as a template.  Defaults to the HOBL spreadsheet in the docs directory.  This is the spreadsheet that should be used for any valid HOBL study.
        1. goals - Path to a .csv file that contains the targets for each metric/scenario in the templates Scorecard sheet.
        1. name - An optional name for the resulting spreadsheet.  Default is the study name (derived from the parent directory) followed by "_study_report.xlsx".
        1. battery_capacity - Typical battery capacity in Wh.

## Log file
* A hobl.log file is created and written to during the test execution in the scenario run folder.  Lines are categorized as INFO, DEBUG, and ERROR.  INFO relays what the scenario is doing at a high level.  DEBUG is for seeing the details of what is actually happening.  And ERROR highlights what went wrong.

## Callbacks
* Callback parameters are provided for interfacing with external equipment, such as DAQs and relays.
* For each scenario there are 3 callbacks:
    1. callback_test_begin
    1. callback_test_end
    1. callback_data_ready
    1. callback_test_fail
* For each of these, a shell command can be specified to be executed.  Typically this would be another script that would trigger DAQ recording, for example.
* The cs_floor and cs_active scenarios also have callback parameters for triggering the button of the device.  Typically this is done via a script that triggers a relay or other IO to activate the power button of the device.
* The charge_on and charge_off scenarios, as well as the auto_recharge and auto_charge tools similarly have callbacks to enable and disable the charger.

## Config Check
* By default, each non-prep scenario run will run the "config_check" script to get system configuration information to add to the results report.
* Further, a pre-run and post-run small config_check is run before and after the test respectively.  This helps capture any changes in screen brightness, volume, radios, etc.
* This can be disabled by setting global:config_check to 0.

## Graphic User Interface
* Documentation of the HOBLweb UI can be found here: [HOBL UI](HOBL_UI.md)

## Test Plans
* A "test plan" is simply a sequence of runs that make up a study.
* The "New Job" page in the HOBL UI allows you to load existing test plans, amend them, or create new test plans by adding scenarios.
* Each line specified the scenario to run, with options to change the number of iterations, change the tools, or override parameters.
* A pane to set up Study Variables allows more automated generation and organization of advanced studies.
* When submitting a job, the HOBL UI will automatically insert a "prep" scenario run for all the scenarios identified in the job, to make sure they've all been prepped before executing them.

## SimpleRemote
* SimpleRemote is a console application that runs in the background on the DUT to accept network commands (JSON RPC) for executing commands/programs and transferring files.
* Part of dut_setup is to install SimpleRemote and set it to execute automatically upon system boot.
* InputInject is a plugin to SimpleRemote that very efficiently handles injecting keystrokes and mouse clicks on the DUT, as well as taking screen shots for image-based automation.

## Windows Application Driver
* Windows Application Driver is similar to WebDriver, but controls Windows applications or desktop instead of web sites in a browser.
* It uses the same JSON Wire Protocol as webdriver, so the client-side code on the Host is essentially the same, just communicates through a different port.
* On the DUT (server) side, it translates Webdriver commands to Windows UI Automation protocol for controlling apps.
* Scenarios that need WinAppDriver will launch the server on the DUT at the beginning of the scenario and shut it down at the end.
* Use of WinAppDriver is being phased out in favor of image-based automation, using the Scenario Maker tool, as it is no longer being maintained.  Also, WinAppDriver has a power hit, so it's only suitable for prep scenarios.

## Scenario Maker
* Scenario Maker is an application that facilitates the creation of new test scenarios (or editing existing ones).
* Run Scenario Maker by executing hobl\ScenarioMaker\ScenarioMaker.cmd.
* It starts with a remote connection to a DUT (specify IP address in Settings), then allows you to compose a sequence of actions for the scenario using the menu.
* Record mode records you interacting with the DUT as a user would, and generates the appropriate action sequence for the test quickly and easily.  Caution, though, as these won't be optimized for power consumption.  To minimize power consumption, only take new screen captures when what you want to capture wasn't in a previous capture, and only capture as much of the screen as necessary.  Smaller screen region captures are faster and use less power.

