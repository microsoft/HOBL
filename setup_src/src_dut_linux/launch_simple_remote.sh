#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

ARCH="arm64"
if [ "$(uname -m)" = "x86_64" ]; then
    ARCH="x64"
fi

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/home/shared/hobl_bin"

PATH=$PATH:/home/shared/dotnet
export DOTNET_ROOT=/home/shared/dotnet

# Start SimpleRemote
$BIN_DIR/SimpleRemote/SimpleRemoteServer_linux-$ARCH/SimpleRemoteConsole --SuppressUserWarning

