#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"
export SUDO_ASKPASS=$BIN_DIR/get_password.sh
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_pytorch_inf_v2_prep.log"
mkdir -p "$LOG_DIR"

# Python 3.14.8 per the mac_pytorch_inf_v2 design (config.py PYTHON_VERSION).
PYTHON_VERSION="3.14.8"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

check_status() {
    if [ $? -ne 0 ]; then
        log " ERROR - $1 failed"
        exit 1
    fi
    log "✓ $1 successful"
}

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        log "✓ $1 is available"
        return 0
    else
        log " ERROR - $1 is not available"
        return 1
    fi
}

# Always copy resources to pick up script/config changes
log "-- Copying resources to $BIN_DIR/mac_pytorch_inf_v2_resources"
SRC_RES_DIR="$(cd "$(dirname "$0")" && pwd)"
DST_RES_DIR="$BIN_DIR/mac_pytorch_inf_v2_resources"
mkdir -p "$DST_RES_DIR"
check_status "resource directory creation"
if [ "$SRC_RES_DIR" = "$DST_RES_DIR" ]; then
    log "✓ Resource copy skipped (already running from $DST_RES_DIR)"
else
    cp -r "$SRC_RES_DIR"/* "$DST_RES_DIR/"
    check_status "resource copy"
fi

echo "-- mac_pytorch_inf_v2_prep.sh started $(date)" > "$LOG_FILE"
log "-- mac_pytorch_inf_v2 prep started"

# Check if BIN_DIR exists
if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - $BIN_DIR does not exist"
    exit 1
fi

# --- Install Homebrew ---
log "-- Installing Brew"
if [ -x /opt/homebrew/bin/brew ]; then
    log "✓ Brew already installed at /opt/homebrew/bin/brew"
else
    export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    check_status "Brew installation"
fi

if [ ! -x /opt/homebrew/bin/brew ]; then
    log " ERROR - Homebrew not found at /opt/homebrew/bin/brew"
    exit 1
fi
eval "$(/opt/homebrew/bin/brew shellenv)"

log "-- Installing readline and xz"
brew install readline xz
check_status "readline and xz installation"

# --- Install pyenv ---
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

check_command "pyenv" || exit 1

# --- Install Python (conditional -- DO NOT use -f) ---
# Force-reinstall (`pyenv install -f`) wipes the pyenv version directory,
# including any packages another scenario installed into it. Multiple HOBL
# scenarios share pyenv-managed Python versions, so always check first and
# only install when the version is genuinely missing (see
# copilot-instructions.md "Shared-State Hazards Across Scenarios").
log "-- Checking for Python $PYTHON_VERSION"
if pyenv versions --bare | grep -qx "$PYTHON_VERSION"; then
    log "✓ Python $PYTHON_VERSION already installed via pyenv -- preserving existing install"
else
    log "-- Installing Python $PYTHON_VERSION"
    pyenv install "$PYTHON_VERSION"
    check_status "Python $PYTHON_VERSION installation"
fi

log "-- Setting Python version"
pyenv global "$PYTHON_VERSION"
check_status "Setting Python global version"

# Verify Python version
PYTHON_ACTIVE_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_ACTIVE_VERSION" != "$PYTHON_VERSION" ]; then
    log " ERROR - Python version is $PYTHON_ACTIVE_VERSION, expected $PYTHON_VERSION"
    pyenv versions
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_ACTIVE_VERSION"
log "Python path: $(which python)"

# --- CD to resources ---
log "-- CD to resources"
cd "$BIN_DIR/mac_pytorch_inf_v2_resources"
if [ $? -ne 0 ]; then
    log " ERROR - Failed to change directory to $BIN_DIR/mac_pytorch_inf_v2_resources"
    exit 1
fi

if [ ! -f "requirements_osx.txt" ]; then
    log " ERROR - requirements_osx.txt file not found"
    exit 1
fi

# --- Create per-scenario venv ---
# Packages live in this scenario's private venv, NOT the shared pyenv
# site-packages, so another scenario's `pyenv install`/`pyenv global` cannot
# disturb mac_pytorch_inf_v2's dependencies (e.g. torch/transformers/mlx).
VENV_DIR="$BIN_DIR/mac_pytorch_inf_v2_resources/.venv"
PYENV_PYTHON=$(pyenv which python 2>/dev/null)
if [ -z "$PYENV_PYTHON" ] || [ ! -x "$PYENV_PYTHON" ]; then
    log " ERROR - pyenv python not found; pyenv install may have failed"
    exit 1
fi
log "Base pyenv python: $PYENV_PYTHON"

if [ -d "$VENV_DIR" ]; then
    log "Removing existing venv to ensure clean rebuild: $VENV_DIR"
    rm -rf "$VENV_DIR"
fi
log "Creating venv at: $VENV_DIR"
"$PYENV_PYTHON" -m venv "$VENV_DIR"
check_status "venv creation"

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
if [ ! -x "$VENV_PYTHON" ]; then
    log " ERROR - venv python missing after venv creation: $VENV_PYTHON"
    exit 1
fi
log "Venv python: $VENV_PYTHON"

# --- Install Python packages (into the venv, never the shared pyenv env) ---
log "-- Installing Python packages from requirements_osx.txt into venv"
"$VENV_PIP" install -r requirements_osx.txt
check_status "Python package installation"

# --- Download model weights (using venv python so torch/mlx are available) ---
# Cache/download happens here, outside any scored time in the run script.
log "-- Downloading portable + quantized headline model weights"
"$VENV_PYTHON" run_benchmark.py --setup --model-tier portable
check_status "portable model download"
"$VENV_PYTHON" run_benchmark.py --setup --model-tier quantized
check_status "quantized model download"

log "-- mac_pytorch_inf_v2 prep completed"
exit 0
