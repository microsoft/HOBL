#!/bin/zsh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# AI Foundry Local run script for macOS
# Runs inference with the specified model and prompt.

LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_foundrylocal_run.log"
MODEL="${1:-qwen2.5-0.5b}"
PROMPT="${2:-What is the meaning of life?}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOTNET="$SCRIPT_DIR/foundrylocal_app/.dotnet/dotnet"
APP_DLL="$SCRIPT_DIR/foundrylocal_app/publish/FoundryLocalWorkload.dll"

PROMPT=$(echo "$PROMPT" | sed 's/^"//;s/"$//')
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

echo "-- Foundry Local run started" > "$LOG_FILE"
log "-- Foundry Local run started"

ARCH=$(uname -m)
log "Detected architecture: $ARCH"
log "Model: $MODEL"
log "Prompt: $PROMPT"

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

log "Running inference..."
log "Running Foundry Local SDK inference for model: $MODEL"

zmodload zsh/datetime
START_TIME=$EPOCHREALTIME

OUTPUT_FILE="$LOG_DIR/mac_foundrylocal_output.txt"
"$DOTNET" "$APP_DLL" run "$MODEL" "$PROMPT" > "$OUTPUT_FILE" 2>&1
EXIT_CODE=$?

END_TIME=$EPOCHREALTIME
DURATION=$((END_TIME - START_TIME))

log ""
log "=== Model Output ==="
while IFS= read -r line; do log "  $line"; done < "$OUTPUT_FILE"
log "===================="

check $EXIT_CODE

SCENARIO_RUNTIME=$(printf "%.2f" "$DURATION")
log ""
log "Scenario completed in $SCENARIO_RUNTIME seconds"

RESULTS_FILE="$LOG_DIR/mac_foundrylocal_results.csv"
cat > "$RESULTS_FILE" << EOF
scenario_runtime,$SCENARIO_RUNTIME
architecture,$ARCH
ai_model,$MODEL
prompt,$PROMPT
EOF

log "Results saved to: $RESULTS_FILE"
log ""
log "========================================"
log "Foundry Local run completed successfully"
log "Model: $MODEL"
log "Scenario runtime: $SCENARIO_RUNTIME seconds"
log "========================================"
log "Log file: $LOG_FILE"

exit 0
