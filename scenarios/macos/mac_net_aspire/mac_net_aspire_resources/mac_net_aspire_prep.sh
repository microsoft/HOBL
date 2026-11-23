#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"
export SUDO_ASKPASS=$BIN_DIR/get_password.sh
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_net_aspire_prep.log"
DOTNET_SDK_VERSION="11.0.100"
mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

# Helper function for error checking
check_status() {
    if [ $? -ne 0 ]; then
        log " ERROR - $1 failed"
        exit 1
    fi
    log "✓ $1 successful"
}

# Helper function to verify command exists
check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        log "✓ $1 is available"
        return 0
    else
        log " ERROR - $1 is not available"
        return 1
    fi
}

echo "-- mac_net_aspire_prep.sh started $(date)" > "$LOG_FILE"
log "-- net_aspire prep started"

# Check if BIN_DIR exists
if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - $BIN_DIR does not exist"
    exit 1
fi
log "✓ BIN_DIR exists: $BIN_DIR"

# Installing XCode tools
log "-- Installing XCode tools"
if xcode-select -p >/dev/null 2>&1; then
    log "✓ XCode tools already installed"
else
    xcode-select --install 2>/dev/null || true
    
    # Wait for installation to complete (up to 10 minutes)
    log "Waiting for XCode tools installation to complete..."
    MAX_WAIT=600
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        if xcode-select -p >/dev/null 2>&1; then
            log "✓ XCode tools installation completed"
            break
        fi
        sleep 10
        ELAPSED=$((ELAPSED + 10))
        log "  Still waiting... ($ELAPSED seconds elapsed)"
    done
    
    if ! xcode-select -p >/dev/null 2>&1; then
        log " ERROR - XCode tools installation did not complete within $MAX_WAIT seconds"
        exit 1
    fi
fi

# Installing Rosetta 2
# The Aspire build invokes grpc.tools' protoc, which Homebrew/NuGet ship only as
# an x86_64 binary (tools/macosx_x64/protoc). On Apple Silicon without Rosetta 2
# this fails with "Bad CPU type in executable" (Win32Exception 86) during the
# ConfigurationSchema regeneration build. Rosetta lets the x86_64 protoc run
# under emulation; protoc is a build-time codegen tool only and is not part of
# the timed workload, so this does not affect benchmark results.
log "-- Installing Rosetta 2"
if /usr/bin/pgrep -q oahd; then
    log "✓ Rosetta 2 already installed"
else
    sudo -A softwareupdate --install-rosetta --agree-to-license
    check_status "Rosetta 2 installation"
fi

cd $BIN_DIR || {
    log " ERROR - Failed to change to $BIN_DIR"
    exit 1
}

# Clone repo (or verify it exists)
log "-- Cloning repo"
if [ -d "$BIN_DIR/aspire" ]; then
    log "✓ Aspire repo already exists"
    cd $BIN_DIR/aspire
else
    git clone https://github.com/dotnet/aspire.git
    check_status "Git clone"
    cd $BIN_DIR/aspire
fi

log "-- Checkout version 9.4.2"
git checkout v9.4.2
check_status "Git checkout v9.4.2"

# Install Brew (or verify it exists at default location)
log "-- Installing Brew"
if [ -x /opt/homebrew/bin/brew ]; then
    log "✓ Brew already installed at /opt/homebrew/bin/brew"
else
    export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    check_status "Brew installation"
fi

# Verify brew is installed at expected location
if [ ! -x /opt/homebrew/bin/brew ]; then
    log " ERROR - Homebrew not found at /opt/homebrew/bin/brew"
    exit 1
fi
log "✓ Homebrew verified at /opt/homebrew/bin/brew"
eval "$(/opt/homebrew/bin/brew shellenv)"

log "-- Installing readline and xz"
brew install readline xz
check_status "readline and xz installation"

log "-- Installing npm"
brew install npm
check_status "npm installation"
check_command "npm" || exit 1

log "-- Installing pyenv"
brew install pyenv pyenv-virtualenv
check_status "pyenv installation"

log "-- Modifying profile"

# Add brew shellenv if not already there
if ! grep -q 'eval "$(/opt/homebrew/bin/brew shellenv)"' ~/.zprofile 2>/dev/null; then
    echo '# brew variables and PATH' >> ~/.zprofile
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    log "✓ Added brew to profile"
else
    log "✓ brew already in profile"
fi

# Add pyenv init if not already there
if ! grep -q "pyenv init" ~/.zprofile 2>/dev/null; then
    echo '# for pyenv and pyenv-virtualenv' >> ~/.zprofile
    echo 'eval "$(pyenv init -)"' >> ~/.zprofile
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.zprofile
    log "✓ Added pyenv to profile"
else
    log "✓ pyenv already in profile"
fi

# Source profile to load environment
source ~/.zprofile

# Verify pyenv is available
check_command "pyenv" || exit 1

log "-- Installing Python 3.12.10"
pyenv install 3.12.10 -f
check_status "Python 3.12.10 installation"

log "-- Setting Python version"
pyenv global 3.12.10
check_status "Setting Python global version"

# Increase Playwright browser download timeout (default is too short for slow CDN)
export PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000
log "-- Set PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 (5 minutes)"

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_VERSION" != "3.12.10" ]; then
    log " ERROR - Python version is $PYTHON_VERSION, expected 3.12.10"
    pyenv versions
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_VERSION"

log "-- Pinning Aspire to stable .NET SDK $DOTNET_SDK_VERSION"
python - "$BIN_DIR/aspire/global.json" "$DOTNET_SDK_VERSION" <<'PYSDK'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
config["sdk"]["version"] = sys.argv[2]
config["sdk"]["rollForward"] = "disable"
config["sdk"]["allowPrerelease"] = False
config["tools"]["dotnet"] = sys.argv[2]
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PYSDK
check_status "Configuring Aspire .NET SDK"

# -------------------------------------------------------------------
# Regenerate ConfigurationSchema.json files
# -------------------------------------------------------------------
# The Aspire repo validates that checked-in ConfigurationSchema.json files match
# what the installed SDK generates. A plain build fails validation if they differ.
# The Aspire CI runs with /p:UpdateConfigurationSchema=true to regenerate them
# before validation. We do the same here during prep so that subsequent run
# iterations (which use plain --build) pass cleanly.
log "-- Regenerating ConfigurationSchema.json files"
cd $BIN_DIR/aspire
# Capture build output so a failure is diagnosable. Without this the entire
# MSBuild/dotnet error was swallowed and the prep log only said
# "ConfigurationSchema regeneration failed" with no further clues.
ASPIRE_BUILD_LOG="$LOG_DIR/mac_net_aspire_build.log"
log "   build output -> $ASPIRE_BUILD_LOG"
./build.sh --restore --build /p:UpdateConfigurationSchema=true >>"$ASPIRE_BUILD_LOG" 2>&1
ASPIRE_BUILD_RC=$?
if [ $ASPIRE_BUILD_RC -ne 0 ]; then
    log " ERROR - ConfigurationSchema regeneration failed (rc=$ASPIRE_BUILD_RC)."
    log " ERROR - See $ASPIRE_BUILD_LOG for full build output. Last 40 lines:"
    tail -n 40 "$ASPIRE_BUILD_LOG" 2>/dev/null | while IFS= read -r line; do
        log "   | $line"
    done
    exit 1
fi
log "✓ ConfigurationSchema regeneration successful"

log ""
log "✓ All checks passed"
log "-- net_aspire prep completed successfully"
exit 0