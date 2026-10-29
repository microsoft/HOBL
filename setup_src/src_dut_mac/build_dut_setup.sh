#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Create assets folder if it does not exist
if [ ! -d "assets" ]; then
    mkdir assets
fi

# Copy SimpleRemote and InputInject binaries to assets folder
cp ../SimpleRemote/Output/SimpleRemoteServer_osx-arm64/SimpleRemoteConsole_osx-arm64.zip assets/
cp ../InputInject/Output/InputInject_osx-arm64.zip assets/
cp ../ScreenServer/Output/ScreenServer_osx-arm64/ScreenServer_osx-arm64.zip assets/
cp ../brightness/brightness assets/
cp -R ../remote.app assets/

# Copy desktop images to assets folder
cp -r ../DesktopImages assets/

# Copy the install script to assets folder
cp dut_setup_install.sh assets/

# Copy launch script to assets folder
cp launch_simple_remote.sh assets/

# Copy launch plist to assets folder
cp simple_remote.plist assets/

# Copy certificates to assets folder
cp certs/root_cert.pem assets/
cp certs/int_cert.pem assets/

# Create self-extracting archive
./makeself.sh assets dut_setup.sh "HOBL DUT Setup" ./dut_setup_install.sh