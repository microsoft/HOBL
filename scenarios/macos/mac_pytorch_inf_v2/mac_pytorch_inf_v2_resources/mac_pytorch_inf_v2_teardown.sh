#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_pytorch_inf_v2_teardown.log"
PYTHON_VERSION="3.14.8"
mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

# Create assets folder if it does not exist
if [ ! -d "$BIN_DIR" ]; then
    mkdir "$BIN_DIR"
fi

echo "-- mac_pytorch_inf_v2_teardown.sh started $(date)" > "$LOG_FILE"
log "-- mac_pytorch_inf_v2 teardown started"

# Source profile to load brew + pyenv
log "-- Loading environment"
if [ -f ~/.zprofile ]; then
    source ~/.zprofile
else
    log " ERROR - ~/.zprofile not found"
    exit 1
fi

log "-- Setting Python version"
pyenv global "$PYTHON_VERSION"

log "-- CD to resources"
cd "$BIN_DIR/mac_pytorch_inf_v2_resources"

log "-- Cleanup GPU caching"
# Use the per-scenario venv python (created during prep) rather than the
# shared pyenv python. The venv has torch/mlx installed; the shared pyenv
# environment may not after other scenarios run.
VENV_PYTHON="$BIN_DIR/mac_pytorch_inf_v2_resources/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    log "-- venv missing at $VENV_PYTHON; skipping GPU cleanup (will be recreated on next prep)"
    exit 0
fi
"$VENV_PYTHON" run_benchmark.py --cleanup-gpu
# Don't treat cleanup failure as fatal -- teardown should not break the run cycle.
if [ $? -ne 0 ]; then
    log "-- GPU cleanup returned a non-zero exit code (non-fatal)"
fi

log "-- mac_pytorch_inf_v2 teardown completed"
exit 0
