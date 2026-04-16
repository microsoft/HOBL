# HOBL

## Introduction

* "HOBL" (Hours Of Battery Life) is a test framework and set of test scenarios for the purpose of measuring power, perfromance, and thermal characteristics of Windows and (to a lesser extent) macOS devices.
* The intent of HOBL is to support fully-automated and scaled out user-representative test execution and analysis, to enable computer system and component manufacturers to validate and tune products during development.
* Power is expected to be primarily measured with external DAQ equipement, but internal power monitor chips and battery rundown measurements are also supported.
* The HOBL test framework runs on a "Host" Windows 10/11 PC.  Test scenarios execute on the Host and send commands to the DUT (Device Under Test) over a local network to replicate user interactions.
* To ensure standardized and representative measurements, testers must not kill or disable processes or services.  "Prep scenarios" will be automatically executed to put the system in a controlled state suitable for testing.
* **Make sure your DUT is a computer that is ONLY logged in with a dedicated test account.**  Files, emails, etc, may be deleted.  A work or personal computer may be used as a "Host", but not a "DUT".
* For questions or issues, send mail to [HOBLsupport@microsoft.com](mailto:HOBLsupport@microsoft.com).  Attach the hobl.log file and relevant screen shots for any problematic test run.

### Quick Start for experienced HOBL users (novice users please read full [Setup](docs/support/docs/HOBL_Setup.md) instructions)
* Make sure Git for Windows is installed on HOBL Host.
* Clone repo (preferrably to c:\hobl, to avoid appsettings.json tweaks).
* Run host_setup.exe, located in the root folder.  Select both options.
* Copy downloads\setup\dut_setup_\<ver\>.exe to a flash drive and run it on the DUT.  This will install SimpleRemote and configure the DUT for communication with the HOBL Host.  HOBL can't communicate without this, and you will see errors about failed remote directory creation and communication timeouts.
* Verify network connectivity by pinging the DUT from the Host and vice versa.  Then run the comm_check scenario and make sure all checks pass.
* To get HOBL updates, do a "git pull".
* To get HOBL UI updates, run host_setup.exe and only select the "User Interface" option.

### Further reading:
* [Setup](docs/support/docs/HOBL_Setup.md)
* [Usage](docs/support/docs/HOBL_Usage.md)
* [System Preparation](docs/support/docs/HOBL_Prep.md)
* [Scenarios](docs/support/docs/HOBL_Scenarios.md)
* [Tools](docs/support/docs/HOBL_Tools.md)
* [Creating Scenarios](docs/support/docs/HOBL_ScenarioMaker.md)
* [HOBL Design Philosophy](docs/support/docs/HOBL_DesignPhilosophy.md)

# Security

HOBL uses [SimpleRemote](https://github.com/Microsoft/SimpleRemote) for communicating with devices, which allows users to run programs and access files on the computer where it is run, with no authentication whatsoever. It was desiged to be run on test machines on closed, lab networks.

# License

This project is licensed under the MIT License.  
See the [LICENSE](LICENSE) file for details.

---

## Utilities Folder

This folder contains executable utilities required by this project. 
These utilities fall into three categories:

1. **Microsoft Proprietary Utilities**
   - Located in: `/utilities/proprietary/`
   - License: Microsoft Proprietary License
   - Source code: Not open source
   - Modification, reverse engineering, or redistribution outside this project is prohibited.

2. **Open-Source Utilities (Redistributable)**
   - Located in: `/utilities/open_source/`
   - These utilities are governed by their associated open-source licenses, included in each 
     subfolder's `LICENSE` file.

3. **Third-Party Open-Source Utilities**
   - Located in: `/utilities/third_party/`
   - These utilities are governed by their associated open-source licenses, included in each 
     subfolder's `LICENSE` file.

Each utility’s license type, ownership, and usage permissions are stated explicitly in its 
respective subfolder. See `NOTICE.md` at the repository root for consolidated 
third-party licensing information when applicable.

## Third‑Party Software Notices

This project includes or depends upon third‑party software components licensed under open source licenses.  
The following notices are provided for attribution and license compliance purposes.  These components are found in the `utilities/third_party` folder.

### MIT Licensed Components

The following components are licensed under the MIT License:

- **diskspd**  
  Copyright © 2014 Microsoft  
  License: MIT  
  Source: [https://github.com/microsoft/diskspd](https://github.com/microsoft/diskspd)

- **tee**  
  Copyright © uutils developers  
  License: MIT  
  Source: [https://github.com/uutils/coreutils/tree/main/src/uu/tee](https://github.com/uutils/coreutils/tree/main/src/uu/tee)

A copy of the MIT License is provided in the applicable component directory.

---

### Apache License 2.0 Components

The following components are licensed under the Apache License, Version 2.0:

- **PolicyFileEditor**  
  Copyright © 2015 Dave Wyatt  
  License: Apache License 2.0  
  Source: [https://www.powershellgallery.com/packages/PolicyFileEditor/3.0.1](https://www.powershellgallery.com/packages/PolicyFileEditor/3.0.1)

These components are used in compliance with the Apache License, Version 2.0.  
A copy of the license is available at:  
https://www.apache.org/licenses/LICENSE-2.0

If required by a specific component, any applicable NOTICE files are included in the repository.

---

###  GPL Version 2.0 Components

The following components are licensed under the GPL License, Version 2.0:

- **Remote**  
  Copyright © Microsoft  
  License: GPL 2.0  
  Source: Supplied


If required by a specific component, any applicable NOTICE files are included in the repository.

---

## Attribution and Trademarks

Third‑party project names and trademarks are the property of their respective owners.  
Use of these names does not imply endorsement.

---

## Source Availability

This repository does not modify the licensing terms of any included third‑party software.  
All third‑party components remain subject to their original license terms.

---