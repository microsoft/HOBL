#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

LOOPS="${1:-5}"
RELOAD_MODE="${2:-none}"
PORT="${3:-8765}"
BIN_DIR="/Users/Shared/hobl_bin"
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_fast_api_app_run.log"
METRICS_FILE="$LOG_DIR/mac_fast_api_app_results.csv"
DETAIL_DIR="$LOG_DIR/mac_fast_api_app_detail"
APP_DIR="$BIN_DIR/fast_api_app_workload"
TOOLS_DIR="$BIN_DIR/mac_fast_api_app_tools/.venv"
TOOLS_PYTHON="$TOOLS_DIR/bin/python"
TOOLS_UV="$TOOLS_DIR/bin/uv"

mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

fail() {
    log " ERROR - $1"
    exit 1
}

echo "-- FastAPI app run started $(date)" > "$LOG_FILE"

if [ -f "$HOME/.zprofile" ]; then
    . "$HOME/.zprofile"
fi

case "$LOOPS" in
    ''|*[!0-9]*) fail "Loops must be a positive integer" ;;
    0) fail "Loops must be at least 1" ;;
esac
case "$RELOAD_MODE" in
    none|managed|external) ;;
    *) fail "Unsupported reload mode: $RELOAD_MODE" ;;
esac

[ -x "$TOOLS_PYTHON" ] || fail "Tools Python missing: $TOOLS_PYTHON. Re-prep required."
[ -x "$TOOLS_UV" ] || fail "uv missing: $TOOLS_UV. Re-prep required."
[ -f "$APP_DIR/benchmark_inner_loop.py" ] || fail "Benchmark harness missing: $APP_DIR"

if ! command -v pyenv >/dev/null 2>&1; then
    fail "pyenv is not available. Re-prep required."
fi
export PYENV_VERSION="3.12.10"
PYENV_PYTHON="$(pyenv which python 2>/dev/null)"
[ -x "$PYENV_PYTHON" ] || fail "pyenv python not found at: $PYENV_PYTHON"
[ "$("$PYENV_PYTHON" --version 2>&1)" = "Python 3.12.10" ] ||
    fail "Expected Python 3.12.10"

rm -rf "$DETAIL_DIR"
mkdir -p "$DETAIL_DIR"
HARNESS_LOG="$LOG_DIR/mac_fast_api_app_harness.log"
"$TOOLS_PYTHON" "$APP_DIR/benchmark_inner_loop.py" \
    --output "$DETAIL_DIR" \
    --uv "$TOOLS_UV" \
    --python "$PYENV_PYTHON" \
    --loops "$LOOPS" \
    --port "$PORT" \
    --reload-mode "$RELOAD_MODE" > "$HARNESS_LOG" 2>&1 ||
    fail "FastAPI app benchmark failed. See $HARNESS_LOG for details."

[ -f "$DETAIL_DIR/metrics.csv" ] ||
    fail "Harness did not produce metrics: $DETAIL_DIR/metrics.csv"
cp "$DETAIL_DIR/metrics.csv" "$METRICS_FILE" ||
    fail "Failed to save HOBL metrics"

log ""
log "========================================"
log "FastAPI Application Developer Metrics"
log "========================================"
while IFS= read -r line; do
    log "$line"
done < "$METRICS_FILE"
log "========================================"
log "Metrics saved to: $METRICS_FILE"
exit 0
