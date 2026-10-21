#!/bin/zsh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# AI Foundry Local teardown script for macOS
# Removes only the model cached by the workload.

LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_foundrylocal_teardown.log"
MODEL="${1:-qwen2.5-0.5b}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOTNET="$SCRIPT_DIR/foundrylocal_app/.dotnet/dotnet"
APP_DLL="$SCRIPT_DIR/foundrylocal_app/publish/FoundryLocalWorkload.dll"

mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

echo "-- Foundry Local teardown started" > "$LOG_FILE"
log "-- Foundry Local teardown started"
log "Model to remove: $MODEL"
log "Removing model from cache..."

if [ -x "$DOTNET" ] && [ -f "$APP_DLL" ]; then
    log "Running SDK teardown for model: $MODEL"
    OUTPUT=$("$DOTNET" "$APP_DLL" teardown "$MODEL" 2>&1)
    EXIT_CODE=$?
    echo "$OUTPUT" | while IFS= read -r line; do log "  $line"; done

    if [ "$EXIT_CODE" -eq 0 ]; then
        log "Model removed successfully"
    else
        log "Warning: Model removal returned exit code $EXIT_CODE (model may not have been cached)"
    fi
else
    log "Warning: Foundry Local workload app or per-scenario dotnet not found, skipping cache removal"
fi

log ""
log "========================================"
log "Foundry Local teardown completed"
log "========================================"
log "Log file: $LOG_FILE"

exit 0
