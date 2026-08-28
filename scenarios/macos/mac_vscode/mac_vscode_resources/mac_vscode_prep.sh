#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

BIN_DIR="/Users/Shared/hobl_bin"
export SUDO_ASKPASS=$BIN_DIR/get_password.sh
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_vscode_prep.log"
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

echo "-- mac_vscode_prep.sh started $(date)" > "$LOG_FILE"
log "-- vscode prep started"

# Detect processor architecture
ARCH=$(uname -m)
log "-- Detected architecture: $ARCH"

if [ "$ARCH" != "arm64" ]; then
    log " ERROR - This script is for Apple Silicon (ARM64) only. Detected: $ARCH"
    exit 1
fi

if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - $BIN_DIR does not exist"
    exit 1
fi

# Always copy resources to pick up script/config/patch changes.
# This keeps prep resilient when invoked from different working directories
# while still expecting files under $BIN_DIR/mac_vscode_resources.
log "-- Copying resources to $BIN_DIR/mac_vscode_resources"
SRC_RES_DIR="$(cd "$(dirname "$0")" && pwd)"
DST_RES_DIR="$BIN_DIR/mac_vscode_resources"
mkdir -p "$DST_RES_DIR"
check_status "resource directory creation"
if [ "$SRC_RES_DIR" = "$DST_RES_DIR" ]; then
    log "✓ Resource copy skipped (already running from $DST_RES_DIR)"
else
    cp -r "$SRC_RES_DIR"/* "$DST_RES_DIR/"
    check_status "resource copy"
fi

cd $BIN_DIR || { log " ERROR - Failed to change to $BIN_DIR"; exit 1; }

# 1. Ensure Xcode command-line tools are installed
log "-- Checking Xcode command-line tools"
if ! xcode-select -p >/dev/null 2>&1; then
    log "-- Installing Xcode command-line tools..."
    xcode-select --install
    log " ERROR - Please complete the Xcode installation dialog and re-run this script"
    exit 1
else
    log "✓ Xcode command-line tools already installed"
fi

# 2. Install Homebrew (if not already installed)
log "-- Checking Homebrew installation"
if [ -x /opt/homebrew/bin/brew ]; then
    log "✓ Brew already installed at /opt/homebrew/bin/brew"
else
    log "-- Installing Homebrew..."
    export NONINTERACTIVE=1
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    check_status "Brew installation"
fi

if [ ! -x /opt/homebrew/bin/brew ]; then
    log " ERROR - Homebrew not found at /opt/homebrew/bin/brew"
    exit 1
fi
eval "$(/opt/homebrew/bin/brew shellenv)"

# 3. Install Node.js 24.18.0
log "-- Checking Node.js installation"
NODE_VERSION="24.18.0"
NODE_PACKAGE="node-v${NODE_VERSION}.pkg"
NODE_PACKAGE_URL="https://nodejs.org/dist/v${NODE_VERSION}/${NODE_PACKAGE}"
NODE_PACKAGE_SHA256="e5a6701100066156d69da48878e4b95986733b0688e0b83afbe1093778e3fffd"
NODE_PACKAGE_PATH="${TMPDIR:-/tmp}/${NODE_PACKAGE}"

if command -v node >/dev/null 2>&1 && [ "$(node --version)" = "v${NODE_VERSION}" ]; then
    log "✓ Node.js ${NODE_VERSION} already installed: $(node --version)"
else
    log "-- Installing Node.js ${NODE_VERSION}..."
    brew list --formula | grep -E '^node(@.*)?$' | while read -r formula; do
        brew unlink "$formula" >/dev/null 2>&1 || true
    done
    curl -fL "$NODE_PACKAGE_URL" -o "$NODE_PACKAGE_PATH"
    check_status "Node.js ${NODE_VERSION} download"
    echo "${NODE_PACKAGE_SHA256}  ${NODE_PACKAGE_PATH}" | shasum -a 256 -c -
    check_status "Node.js ${NODE_VERSION} checksum verification"
    sudo -A installer -pkg "$NODE_PACKAGE_PATH" -target /
    check_status "Node.js ${NODE_VERSION} installation"
    rm -f "$NODE_PACKAGE_PATH"
    hash -r
fi
check_command "node" || exit 1
if [ "$(node --version)" != "v${NODE_VERSION}" ]; then
    log " ERROR - Node.js version is $(node --version), expected v${NODE_VERSION}"
    exit 1
fi
log "-- Node.js version: $(node --version)"

# 4. Install readline and xz (needed for pyenv Python builds)
log "-- Installing readline and xz"
brew install readline xz
check_status "readline and xz installation"

# 5. Install pyenv and Python
log "-- Checking pyenv installation"
if ! command -v pyenv >/dev/null 2>&1; then
    log "-- Installing pyenv and pyenv-virtualenv..."
    brew install pyenv pyenv-virtualenv
    check_status "pyenv installation"
fi

log "-- Modifying profile"
if ! grep -q 'eval "$(/opt/homebrew/bin/brew shellenv)"' ~/.zprofile 2>/dev/null; then
    echo '# brew variables and PATH' >> ~/.zprofile
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
fi

if ! grep -q "pyenv init" ~/.zprofile 2>/dev/null; then
    echo '# for pyenv and pyenv-virtualenv' >> ~/.zprofile
    echo 'eval "$(pyenv init -)"' >> ~/.zprofile
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.zprofile
fi

source ~/.zprofile
check_command "pyenv" || exit 1

log "-- Installing Python 3.12.10"
pyenv install 3.12.10 -f
check_status "Python 3.12.10 installation"

log "-- Setting Python version"
pyenv global 3.12.10
check_status "Setting Python global version"

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_VERSION" != "3.12.10" ]; then
    log " ERROR - Python version is $PYTHON_VERSION, expected 3.12.10"
    pyenv versions
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_VERSION"

# 6. Clone VS Code repository
VSCODE_DIR="$BIN_DIR/vscode"
log "-- Checking VS Code repository"
if [ -d "$VSCODE_DIR" ]; then
    log "✓ VS Code repository already exists at: $VSCODE_DIR"
else
    log "-- Cloning VS Code repository..."
    cd $BIN_DIR || { log " ERROR - Failed to change to $BIN_DIR"; exit 1; }
    git clone https://github.com/microsoft/vscode.git
    check_status "VS Code clone"
fi

cd "$VSCODE_DIR" || { log " ERROR - Failed to change to $VSCODE_DIR"; exit 1; }
log "✓ Current directory: $(pwd)"

# Checkout specific version
log "-- Checking out VS Code version 1.132.0"
git checkout 1.132.0
check_status "VS Code checkout v1.132.0"

# 7. Install npm dependencies
log "-- Installing npm dependencies (this may take 10-20 minutes)..."
# Install deps without lifecycle scripts first so @vscode/spdlog headers are
# guaranteed to exist for patching before node-gyp build kicks in.
NPM_FIRST_LOG="$LOG_DIR/mac_vscode_npm_install_first.log"
log "   phase-1 npm install (--ignore-scripts) output -> $NPM_FIRST_LOG"
npm install --ignore-scripts --loglevel=error >>"$NPM_FIRST_LOG" 2>&1
NPM_FIRST_RC=$?
if [ $NPM_FIRST_RC -ne 0 ]; then
    log " ERROR - First npm install phase failed (rc=$NPM_FIRST_RC)."
    log " ERROR - See $NPM_FIRST_LOG for the underlying error."
    exit 1
fi
log "✓ phase-1 npm install completed"

# Apply a checked-in patch (durable and auditable) instead of ad-hoc string
# replacement in the script. This keeps the workaround deterministic for the
# pinned VS Code tag.
# The fast path below skips this compatibility patch when upstream
# @vscode/spdlog/fmt already builds cleanly on Darwin 25+.
PATCH_FILE="$BIN_DIR/mac_vscode_resources/spdlog_fmt_darwin25.patch"
if [ ! -f "$PATCH_FILE" ]; then
    log " ERROR - Required patch file not found: $PATCH_FILE"
    exit 1
fi

CORE_H="node_modules/@vscode/spdlog/deps/spdlog/include/spdlog/fmt/bundled/core.h"
if [ ! -f "$CORE_H" ]; then
    log " ERROR - Expected spdlog header not found: $CORE_H"
    exit 1
fi

# Fast-path: if this package build already carries the Apple-compatible
# constexpr form, skip patching entirely.
if grep -Eq '^#[[:space:]]*define[[:space:]]+FMT_CONSTEVAL[[:space:]]+constexpr$' "$CORE_H"; then
    log "✓ spdlog/fmt already in compatible state (FMT_CONSTEVAL constexpr)"
else
    log "-- Applying spdlog/fmt compatibility patch: $PATCH_FILE"
    if git apply --check "$PATCH_FILE" >/dev/null 2>&1; then
        git apply "$PATCH_FILE"
        check_status "spdlog/fmt patch apply"
    elif git apply --reverse --check "$PATCH_FILE" >/dev/null 2>&1; then
        log "✓ spdlog/fmt patch already applied"
    else
        # Fallback for minor upstream drift where patch hunk context changed
        # but the required token replacement is still well-defined.
        if grep -Eq '^#[[:space:]]*define[[:space:]]+FMT_CONSTEVAL[[:space:]]+consteval$' "$CORE_H"; then
            log "-- Patch did not apply cleanly; applying tolerant fallback edit in $CORE_H"
            sed -E -i '' 's@^#[[:space:]]*define[[:space:]]+FMT_CONSTEVAL[[:space:]]+consteval$@#  define FMT_CONSTEVAL constexpr@' "$CORE_H"
            check_status "spdlog/fmt fallback edit"
            if grep -Eq '^#[[:space:]]*define[[:space:]]+FMT_CONSTEVAL[[:space:]]+constexpr$' "$CORE_H"; then
                log "✓ spdlog/fmt fallback edit applied"
            else
                log " ERROR - spdlog/fmt fallback edit failed to verify"
                exit 1
            fi
        else
            log " ERROR - spdlog/fmt patch does not apply cleanly and FMT_CONSTEVAL token was not found in core.h"
            exit 1
        fi
    fi
fi

# Rebuild just spdlog with the patched source (npm uses its bundled node-gyp)
log "-- Rebuilding @vscode/spdlog..."
npm rebuild @vscode/spdlog
check_status "spdlog rebuild"

# Re-run npm install to complete any remaining steps (postinstall, etc.)
log "-- Completing npm install..."
NPM_FINAL_LOG="$LOG_DIR/mac_vscode_npm_install_final.log"
log "   phase-2 npm install output -> $NPM_FINAL_LOG"
npm install --loglevel=error >>"$NPM_FINAL_LOG" 2>&1
if [ $? -ne 0 ]; then
    log " ERROR - Final npm install failed."
    log " ERROR - See $NPM_FINAL_LOG for details."
    exit 1
fi
log "✓ npm install successful"

log ""
log "✓ All checks passed"
log "-- vscode prep completed successfully"
exit 0
