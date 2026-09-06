#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"
export SUDO_ASKPASS=$BIN_DIR/get_password.sh
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_fast_api_prep.log"
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

echo "-- mac_fast_api_prep.sh started $(date)" > "$LOG_FILE"
log "-- fast_api prep started"

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
    MAX_WAIT=600  # 10 minutes
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
    
    # Final verification
    if ! xcode-select -p >/dev/null 2>&1; then
        log " ERROR - XCode tools installation did not complete within $MAX_WAIT seconds"
        log "Please install XCode tools manually and re-run this script"
        exit 1
    fi
fi

cd $BIN_DIR || {
    log " ERROR - Failed to change to $BIN_DIR"
    exit 1
}

# Clone repo (or verify it exists)
log "-- Cloning repo"
if [ -d "$BIN_DIR/fastapi" ]; then
    log "✓ FastAPI repo already exists"
    cd $BIN_DIR/fastapi
    git pull origin main 2>/dev/null || true
else
    git clone https://github.com/fastapi/fastapi.git
    check_status "Git clone"
    cd $BIN_DIR/fastapi
fi

log "-- Checkout version 0.119.1"
TARGET_VERSION="0.119.1"

# Ensure tags are available for checkout on existing repos
git fetch --tags --force 2>/dev/null || true

if [ ! -d ".git" ]; then
    log " ERROR - $BIN_DIR/fastapi is not a git repository"
    exit 1
fi

if git rev-parse -q --verify "refs/tags/$TARGET_VERSION" >/dev/null; then
    git checkout "tags/$TARGET_VERSION"
    check_status "Git checkout $TARGET_VERSION"
else
    log " ERROR - FastAPI tag not found: $TARGET_VERSION"
    log "Available matching tags:"
    git tag -l "*${TARGET_VERSION}*" | tail -20
    exit 1
fi

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
if ! pyenv versions --bare | sed 's/^[*[:space:]]*//;s/[[:space:]]*$//' | grep -qx "3.12.10"; then
    pyenv install 3.12.10
    check_status "Python 3.12.10 installation"
else
    log "Python 3.12.10 already installed via pyenv - preserving existing install"
fi

log "-- Setting Python version"
pyenv global 3.12.10
check_status "Setting Python global version"

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_VERSION" != "3.12.10" ]; then
    log " ERROR - Python version is $PYTHON_VERSION, expected 3.12.10"
    pyenv versions
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_VERSION"

log "-- Installing dependencies for FastAPI"
cd $BIN_DIR/fastapi || {
    log " ERROR - Failed to change to fastapi directory"
    exit 1
}

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    log " ERROR - requirements.txt not found"
    exit 1
fi
log "✓ requirements.txt found"

# Microsoft-managed devices block direct access to public PyPI (CISO Central Feed
# Services policy). Install through the approved Microsoft package feed proxy instead.
# Same pinned versions are served, so there is no functional or performance change.
PYPI_INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"
export UV_DEFAULT_INDEX="$PYPI_INDEX_URL"
log "-- Using approved PyPI feed proxy: $PYPI_INDEX_URL"

PYENV_PYTHON="$(pyenv which python 2>/dev/null)"
if [ ! -x "$PYENV_PYTHON" ]; then
    log " ERROR - pyenv python not found at: $PYENV_PYTHON"
    exit 1
fi

VENV_DIR="$BIN_DIR/mac_fast_api_resources/.venv"
rm -rf "$VENV_DIR"
"$PYENV_PYTHON" -m venv "$VENV_DIR"
check_status "FastAPI venv creation"

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

"$VENV_PIP" install --index-url "$PYPI_INDEX_URL" -r requirements.txt
check_status "FastAPI requirements installation"

"$VENV_PIP" install --index-url "$PYPI_INDEX_URL" build "uv==0.9.5"
check_status "Build package installation"

VENV_UV="$VENV_DIR/bin/uv"
if [ ! -x "$VENV_UV" ]; then
    log " ERROR - uv executable missing after installation: $VENV_UV"
    exit 1
fi

UV_PRIME_DIR="$BIN_DIR/mac_fast_api_resources/uv_build_prime"
rm -rf "$UV_PRIME_DIR"
"$VENV_UV" build --out-dir "$UV_PRIME_DIR"
check_status "uv build cache priming"
rm -rf "$UV_PRIME_DIR"

# Final verification
log ""
log "-- Running final verification checks --"
check_command "git" || exit 1
check_command "brew" || exit 1
check_command "npm" || exit 1
check_command "pyenv" || exit 1
if [ ! -x "$VENV_PYTHON" ]; then
    log " ERROR - FastAPI venv python is missing: $VENV_PYTHON"
    exit 1
fi

# Verify FastAPI can be imported
"$VENV_PYTHON" -c "import build, coverage, fastapi, pytest" 2>/dev/null
if [ $? -eq 0 ]; then
    log "✓ FastAPI module can be imported"
else
    log " ERROR - FastAPI module cannot be imported"
    exit 1
fi

log ""
log "✓ All checks passed - Machine is ready to run tests"
log "-- fast_api prep completed successfully"
exit 0