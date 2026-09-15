#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

BIN_DIR="/Users/Shared/hobl_bin"
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_fast_api_app_prep.log"
APP_DIR="$BIN_DIR/fast_api_app_workload"
TOOLS_DIR="$BIN_DIR/mac_fast_api_app_tools/.venv"
INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"

mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

fail() {
    log " ERROR - $1"
    exit 1
}

echo "-- FastAPI app prep started $(date)" > "$LOG_FILE"

resolve_brew() {
    if command -v brew >/dev/null 2>&1; then
        command -v brew
        return
    fi
    if [ -n "${HOMEBREW_PREFIX:-}" ] && [ -x "$HOMEBREW_PREFIX/bin/brew" ]; then
        echo "$HOMEBREW_PREFIX/bin/brew"
        return
    fi
    if command -v mdfind >/dev/null 2>&1; then
        candidate=$(mdfind "kMDItemFSName == 'brew'c" 2>/dev/null |
            awk '/\/bin\/brew$/ {print; exit}')
        if [ -n "$candidate" ]; then
            echo "$candidate"
            return
        fi
    fi
    for root in /opt /usr/local; do
        if [ -d "$root" ]; then
            candidate=$(find "$root" -type f -path '*/bin/brew' -perm -u+x 2>/dev/null |
                head -1)
            if [ -n "$candidate" ]; then
                echo "$candidate"
                return
            fi
        fi
    done
}

BREW="$(resolve_brew)"
if [ -z "$BREW" ]; then
    log "Installing Homebrew..."
    NONINTERACTIVE=1 /bin/bash -c \
        "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" ||
        fail "Homebrew installation failed"
    BREW="$(resolve_brew)"
fi
[ -x "$BREW" ] || fail "Homebrew executable was not found after installation"
log "Using Homebrew: $BREW"
eval "$("$BREW" shellenv)" || fail "Homebrew environment initialization failed"

if ! grep -Fq "$BREW shellenv" "$HOME/.zprofile" 2>/dev/null; then
    printf '\n# HOBL Homebrew environment\neval "$(%s shellenv)"\n' "$BREW" >> "$HOME/.zprofile"
fi

if ! command -v pyenv >/dev/null 2>&1; then
    "$BREW" install pyenv pyenv-virtualenv || fail "pyenv installation failed"
fi

if ! pyenv versions --bare | sed 's/^[*[:space:]]*//;s/[[:space:]]*$//' | grep -qx "3.12.10"; then
    pyenv install 3.12.10 || fail "Python 3.12.10 installation failed"
else
    log "Python 3.12.10 already installed via pyenv - preserving existing install"
fi
export PYENV_VERSION="3.12.10"

PYENV_PYTHON="$(pyenv which python 2>/dev/null)"
[ -x "$PYENV_PYTHON" ] || fail "pyenv python not found at: $PYENV_PYTHON"
log "Using base Python: $PYENV_PYTHON"

rm -rf "$TOOLS_DIR"
"$PYENV_PYTHON" -m venv "$TOOLS_DIR" || fail "Tools venv creation failed"
TOOLS_PIP="$TOOLS_DIR/bin/pip"
TOOLS_UV="$TOOLS_DIR/bin/uv"
"$TOOLS_PIP" install --index-url "$INDEX_URL" "uv==0.9.5" "psutil>=7,<8" ||
    fail "Pinned benchmark tool installation failed"

[ -f "$APP_DIR/uv.lock" ] || fail "Shared FastAPI app workload is missing: $APP_DIR"
cd "$APP_DIR" || fail "Failed to change to $APP_DIR"
rm -rf .venv
log "Priming the locked uv cache outside measurement..."
"$TOOLS_UV" sync --frozen --python "$PYENV_PYTHON" ||
    fail "Locked app sync failed"

APP_PYTHON="$APP_DIR/.venv/bin/python"
"$APP_PYTHON" -c "import fastapi, httptools, pytest, watchfiles; print(fastapi.__version__)" ||
    fail "App dependency validation failed"
rm -rf .venv

log "-- FastAPI app prep completed"
exit 0
