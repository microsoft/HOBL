# HOBL

"HOBL" (Hours Of Battery Life) is a test framework and set of test scenarios for the purpose of measuring power, perfromance, and thermal characteristics of Windows and macOS devices.

[Introduction](docs/support/docs/HOBL.md)

# Security

HOBL uses SimpleRemote for communicating with devices, which allows users to run programs and access files on the computer where it is run, with no authentication whatsoever. It was desiged to be run on test machines on closed, lab networks.

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