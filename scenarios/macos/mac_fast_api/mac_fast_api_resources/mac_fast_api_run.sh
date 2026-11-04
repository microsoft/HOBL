#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

LOG_DIR="/Users/Shared/hobl_data"
BIN_DIR="/Users/Shared/hobl_bin"
SOURCE_DIR="$BIN_DIR/fastapi"
VENV_DIR="$BIN_DIR/mac_fast_api_resources/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_UV="$VENV_DIR/bin/uv"
METRICS_FILE="$LOG_DIR/mac_fast_api_results.csv"
LOG_FILE="$LOG_DIR/mac_fast_api_run.log"

mkdir -p "$LOG_DIR"

log() {
    echo "$1"
    echo "$1" >> "$LOG_FILE"
}

fail() {
    log " ERROR - $1"
    exit 1
}

parse_time_output() {
    time_file="$1"
    prefix="$2"
    [ -f "$time_file" ] || fail "Time log file not found: $time_file"
    real_val=$(awk '/^real / {print $2}' "$time_file")
    user_val=$(awk '/^user / {print $2}' "$time_file")
    sys_val=$(awk '/^sys / {print $2}' "$time_file")
    cputime=$(awk -v user="$user_val" -v sys="$sys_val" 'BEGIN {printf "%.2f", user + sys}')
    eval "${prefix}_time=\$real_val"
    eval "${prefix}_user=\$user_val"
    eval "${prefix}_sys=\$sys_val"
    eval "${prefix}_cputime=\$cputime"
}

run_timed() {
    phase="$1"
    time_file="$2"
    output_file="$3"
    shift 3
    /usr/bin/time -p -o "$time_file" "$@" > "$output_file" 2>&1
    code=$?
    [ "$code" -eq 0 ] || fail "$phase failed. See $output_file for details."
}

echo "-- mac_fast_api maintainer validation started $(date)" > "$LOG_FILE"

[ -d "$SOURCE_DIR" ] || fail "FastAPI source directory not found: $SOURCE_DIR"
[ -x "$VENV_PYTHON" ] || fail "FastAPI venv missing at $VENV_PYTHON. Re-prep required."
[ -x "$VENV_UV" ] || fail "uv missing at $VENV_UV. Re-prep required."

"$VENV_PYTHON" -c "import build, coverage, pytest" >/dev/null 2>&1 ||
    fail "FastAPI maintainer venv has missing or broken packages. Re-prep required."

export PIP_INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"
export UV_DEFAULT_INDEX="$PIP_INDEX_URL"
export PYTHONPATH="./docs_src"
export PYTHONIOENCODING="utf-8"

cd "$SOURCE_DIR" || fail "Failed to change to $SOURCE_DIR"

rm -rf dist
BUILD_LOG="$LOG_DIR/mac_fast_api_build.log"
BUILD_TIME_LOG="$LOG_DIR/mac_fast_api_build_time.log"
log "-- Legacy python -m build output: $BUILD_LOG"
run_timed "python -m build" "$BUILD_TIME_LOG" "$BUILD_LOG" "$VENV_PYTHON" -m build
parse_time_output "$BUILD_TIME_LOG" "build"

rm -rf dist_uv
UV_BUILD_LOG="$LOG_DIR/mac_fast_api_uv_build.log"
UV_BUILD_TIME_LOG="$LOG_DIR/mac_fast_api_uv_build_time.log"
log "-- Modern uv build output: $UV_BUILD_LOG"
run_timed "uv build" "$UV_BUILD_TIME_LOG" "$UV_BUILD_LOG" \
    "$VENV_UV" build --out-dir dist_uv
parse_time_output "$UV_BUILD_TIME_LOG" "uv_build"

TEST_LOG="$LOG_DIR/mac_fast_api_test.log"
TEST_TIME_LOG="$LOG_DIR/mac_fast_api_test_time.log"
log "-- Full coverage test output: $TEST_LOG"
run_timed "FastAPI full coverage tests" "$TEST_TIME_LOG" "$TEST_LOG" \
    "$VENV_PYTHON" -m coverage run -m pytest tests
parse_time_output "$TEST_TIME_LOG" "test"

scenario_runtime=$(awk \
    -v build="$build_time" -v uv="$uv_build_time" -v test="$test_time" \
    'BEGIN {printf "%.2f", build + uv + test}')
architecture=$(uname -m)

log ""
log "========================================"
log "FastAPI Maintainer Release Validation Metrics"
log "========================================"
log "Legacy python -m build: ${build_time}s"
log "Modern uv build:        ${uv_build_time}s"
log "Full coverage tests:    ${test_time}s"
log "scenario_runtime:       ${scenario_runtime}s"
log "========================================"

cat > "$METRICS_FILE" << EOF
scenario_runtime,$scenario_runtime
build_time,$build_time
uv_build_time,$uv_build_time
test_time,$test_time
architecture,$architecture
build_user,$build_user
build_sys,$build_sys
build_cputime,$build_cputime
uv_build_user,$uv_build_user
uv_build_sys,$uv_build_sys
uv_build_cputime,$uv_build_cputime
test_user,$test_user
test_sys,$test_sys
test_cputime,$test_cputime
EOF

log "Metrics saved to: $METRICS_FILE"
exit 0
