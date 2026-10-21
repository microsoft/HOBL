#!/bin/zsh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# AI Foundry Local setup script for macOS
# Downloads the selected model through the Foundry Local SDK.

LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_foundrylocal_setup.log"
MODEL="${1:-qwen2.5-0.5b}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOTNET="$SCRIPT_DIR/foundrylocal_app/.dotnet/dotnet"
APP_DLL="$SCRIPT_DIR/foundrylocal_app/publish/FoundryLocalWorkload.dll"

mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

check() {
    if [ "$1" -ne 0 ]; then
        log " ERROR - Last command failed with exit code: $1"
        exit "$1"
    fi
}

echo "-- Foundry Local setup started" > "$LOG_FILE"
log "-- Foundry Local setup started"

ARCH=$(uname -m)
log "Detected architecture: $ARCH"
log "Model to download: $MODEL"

if [ ! -x "$DOTNET" ]; then
    log " ERROR - Per-scenario dotnet executable not found: $DOTNET"
    log " ERROR - Re-prep is required."
    exit 1
fi

if [ ! -f "$APP_DLL" ]; then
    log " ERROR - Foundry Local workload app not found: $APP_DLL"
    log " ERROR - Re-prep is required."
    exit 1
fi

log "Downloading model to local cache..."
log "Running SDK setup for model: $MODEL"
START_TIME=$(date +%s)

"$DOTNET" "$APP_DLL" setup "$MODEL" 2>&1 | while IFS= read -r line; do log "  $line"; done
check ${pipestatus[1]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log "Model download completed in $DURATION seconds"

log ""
log "========================================"
log "Foundry Local setup completed successfully"
log "Model: $MODEL"
log "Download time: $DURATION seconds"
log "========================================"
log "Log file: $LOG_FILE"

exit 0
