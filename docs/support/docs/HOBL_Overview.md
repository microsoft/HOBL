# HOBL

## Introduction

* "HOBL" (Hours Of Battery Life) is a test framework and set of test scenarios for the purpose of measuring power, performance, and thermal characteristics of Windows and (to a lesser extent) macOS devices.
* The intent of HOBL is to support fully-automated and scaled out user-representative test execution and analysis, to enable computer system and component manufacturers to validate and tune products during development.
* Power is expected to be primarily measured with external DAQ equipment, but internal power monitor chips and battery rundown measurements are also supported.
* The HOBL test framework runs on a "Host" Windows 10/11 PC.  Test scenarios execute on the Host and send commands to the DUT (Device Under Test) over a local network to replicate user interactions.
* To ensure standardized and representative measurements, testers must not kill or disable processes or services.  "Prep scenarios" will be automatically executed to put the system in a controlled state suitable for testing.
* **Make sure your DUT is a computer that is ONLY logged in with a dedicated test account.**  Files, emails, etc, may be deleted.  A work or personal computer may be used as a "Host", but not a "DUT".
* For questions or issues, send mail to [HOBLsupport@microsoft.com](mailto:HOBLsupport@microsoft.com).  Attach the hobl.log file and relevant screen shots for any problematic test run.

### Quick Start for Local Web Browsing Battery Life Testing
* Running locally (meaning HOBL is executing on the device directly with no host) can be useful for short term, one-off testing.  For long-term repeated testing, it's highly recommended to [set up](HOBL_Setup.md) a dedicated HOBL Host computer on a private network.
* For official results, adjust the screen brightness to 150 nits, set Wi-Fi AP to 50 Mbps per client on 5 Ghz, and out-of-box audio volume.  Detailed instructions [here](HOBL_Setup.md#lab-setup).  For quick results, a free app for iPhone and Android called, "Screen Brightness Nits Meter" seems to do reasonably well for measuring screen brightness (be sure to set a white background for measurement).
* Download the [HOBL Installer](https://github.com/microsoft/HOBL/releases/download/hobl_installer/hobl_installer.exe) to the test device (DUT) and execute it.  Select the "Local setup" option.
* After installation, the HOBL UI will open with a `Default` profile that is set up for local rundown testing.
* With the profile selected, select `Web Rundown` from the Quick Launch menu, which can be found either by right-clicking on the profile, or opening the arrow on the `Launch Job` button on the top-right of the window.
* The `rundown_web` test plan will execute and does the following:

    * The `prep` scenario will run some scenarios to prepare the system for web testing.  This includes freshly installing the latest Edge.  Details on system prep can be found [here](HOBL_Prep.md).
    * `charge_on` will turn the charger on if charger automation is set up, or prompt you if not.
    * `wait_for_dut_comm` will wait for communication with DUT.  In case the device is unresponsive in a hosted setup we don't want to continue with the plan.
    * `process_idle_tasks` will let any currently scheduled Windows background tasks complete.  This puts the device in a consistent state at the beginning of any study and is particularly crucial for a freshly installed image which triggers a lot of unrepresentative background tasks, such as Defender and Search indexing.  Normal, representative Defender and Search activity will still occur during the study.  A 2-hour (7200s) timeout is specified, but it shouldn't take more than a few minutes normally.
    * The `recharge` scenario will turn on the charger, wait until battery reaches 100%, wait an additionally 30 minutes (1800s), then turn off the charger to start the rundown.  The 30 min delay can be adjusted with the `post_charge_delay` parameter as desired.
    * The `web` scenario does the actual web browsing, opening 12 different web sites across 7 tabs and interacting with them.  It will loop continually until the device goes into hibernate.  The plan also specifies a screen shot tool that will take screen shots every hour.  This can be helpful to review and make sure pages loaded properly.
    * `charge_on` will again turn on the charger after the rundown, or prompt you to.
    * `study_report` will roll up the results of multiple runs into a single Excel report generated from a template.  A basic template is used by default.  The report will be saved to the specified result directory of the study.

* If you need to stop the rundown:

    * If the HOBL UI is up, click the "Stop Plan" button on the top.
    * If the "web" scenario is running, close the browser and wait a few minutes.  It will detect that it can't navigate the browser, FAIL the test accordingly, and bring up the HOBL UI.

* At the end of the rundown the device will go into hibernate.  Manually reconnect the charger and after about 2 minutes press the power button to bring the device back online.  The device needs to remain in hibernate for at least 2 minutes for it to be detected properly.
* Let the test execution continue.  After a couple minutes the browser should close and the HOB UI will open showing the executing test plan.
* When the plan is completed, you can view detailed result files of the `web` scenario you by clicking on the blue `RunDir` link on that line.  Or, to view a summary of all runs click the `Result Summary` button at the top.  Look for the "Metric > Full Run Duration" for the measured battery life.

### Quick Start for experienced HOBL users (novice users please read full [Setup](HOBL_Setup.md) instructions)
* Make sure Git for Windows is installed on HOBL Host.
* Clone repo (preferably to c:\hobl, to avoid appsettings.json tweaks).
* Run host_setup.exe, located in the root folder.  Select both options.
* Copy downloads\setup\dut_setup_\<ver\>.exe to a flash drive and run it on the DUT.  This will install SimpleRemote and configure the DUT for communication with the HOBL Host.  HOBL can't communicate without this, and you will see errors about failed remote directory creation and communication timeouts.
* Verify network connectivity by pinging the DUT from the Host and vice versa.  Then run the comm_check scenario and make sure all checks pass.
* To get HOBL updates, do a "git pull".
* To get HOBL UI updates, run host_setup.exe and only select the "User Interface" option.

### Further reading:
* [Setup](HOBL_Setup.md)
* [Usage](HOBL_Usage.md)
* [System Preparation](HOBL_Prep.md)
* [Scenarios](HOBL_Scenarios.md)
* [Tools](HOBL_Tools.md)
* [Creating Scenarios](HOBL_ScenarioMaker.md)
* [HOBL Design Philosophy](HOBL_Design_Philosophy.md)

## Security

HOBL uses [SimpleRemote](https://github.com/Microsoft/SimpleRemote) for communicating with devices, which allows users to run programs and access files on the computer where it is run, with no authentication whatsoever. It was designed to be run on test machines on closed, lab networks.
