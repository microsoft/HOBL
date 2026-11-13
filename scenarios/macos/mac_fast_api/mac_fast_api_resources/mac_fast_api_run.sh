#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

WORKERS="${1:-0}"
LOG_DIR="/Users/Shared/hobl_data"
METRICS_FILE="$LOG_DIR/mac_fast_api_results.csv"
LOG_FILE="$LOG_DIR/mac_fast_api_run.log"

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi

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

# Helper function to parse time output and calculate cputime
# Args: $1 = time log file, $2 = phase name prefix (e.g., "build" or "test")
# Sets: <prefix>_real, <prefix>_user, <prefix>_sys, <prefix>_cputime
#
# Time metrics explained:
#   Real - Wall clock time from start to finish of the call. This is all elapsed time
#          including time slices used by other processes and time the process spends
#          blocked (for example if it is waiting for I/O to complete).
#
#   User - The amount of CPU time spent in user-mode code (outside the kernel) within
#          the process. This is only actual CPU time used in executing the process.
#          Other processes and time the process spends blocked do not count towards
#          this figure.
#
#   Sys  - The amount of CPU time spent in the kernel within the process. This means
#          executing CPU time spent in system calls within the kernel, as opposed to
#          library code, which is still running in user-space. Like 'user', this is
#          only CPU time used by the process.
#
#   User+Sys (cputime) - How much actual CPU time your process used. Note that this is
#          across all CPUs, so if the process has multiple threads on a multi-processor
#          system, it could potentially exceed the wall clock time reported by 'Real'.
#          These figures include the 'User' and 'Sys' time of all child processes when
#          they could have been collected (e.g., by wait(2) or waitpid(2)).
#
parse_time_output() {
    local time_file="$1"
    local prefix="$2"
    
    if [ ! -f "$time_file" ]; then
        log " ERROR - Time log file not found: $time_file"
        return 1
    fi
    
    # Parse the -p format output (real, user, sys on separate lines)
    local real_val=$(grep "^real" "$time_file" | awk '{print $2}')
    local user_val=$(grep "^user" "$time_file" | awk '{print $2}')
    local sys_val=$(grep "^sys" "$time_file" | awk '{print $2}')
    
    # Calculate cputime = user + sys
    local cputime=$(echo "$user_val + $sys_val" | bc)
    
    # Export values using eval for dynamic variable names
    eval "${prefix}_real=$real_val"
    eval "${prefix}_user=$user_val"
    eval "${prefix}_sys=$sys_val"
    eval "${prefix}_cputime=$cputime"
    
    log "✓ Parsed $prefix phase: real=${real_val}s, user=${user_val}s, sys=${sys_val}s, cputime=${cputime}s"
}

echo "-- mac_fast_api_run.sh started $(date)" > "$LOG_FILE"
log "-- fast_api run started"

# Source profile
if [ -f ~/.zprofile ]; then
    source ~/.zprofile
    check_status "Loading profile"
else
    echo " ERROR - ~/.zprofile not found"
    exit 1
fi

# Verify required commands are available
log "-- Verifying required commands"
check_command "pyenv" || exit 1
check_command "python" || exit 1
check_command "bash" || exit 1

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin/fastapi"

# Set Python version
log "-- Setting Python version"
pyenv global 3.12.10
check_status "Setting Python global version"
export PYENV_VERSION="3.12.10"

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_VERSION" != "3.12.10" ]; then
    log " ERROR - Python version is $PYTHON_VERSION, expected 3.12.10"
    pyenv versions
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_VERSION"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
check_status "Locating scenario resources"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    log " ERROR - FastAPI scenario environment is missing at $SCRIPT_DIR. Re-prep required."
    exit 1
fi
export VIRTUAL_ENV="$SCRIPT_DIR/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

log "-- Changing directory to: $BIN_DIR"

# Change to fastapi directory
if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - Fast API directory not found: $BIN_DIR"
    log "Please run mac_fast_api_prep.sh first"
    exit 1
fi
log "✓ FastAPI directory exists"

cd $BIN_DIR || {
    log " ERROR - Failed to change to $BIN_DIR"
    exit 1
}
log "✓ Current directory: $(pwd)"

# Verify build and test modules are available
"$VENV_PYTHON" -c "import build, coverage, pytest, fastapi.cli; from fastapi.testclient import TestClient; from coverage.tracer import CTracer"
if [ $? -ne 0 ]; then
    log " ERROR - Required Python build or test modules are not installed"
    log "Please run mac_fast_api_prep.sh first"
    exit 1
fi
log "✓ Build and test modules are available"

# Route PEP 517 build isolation (and any pip invoked by the tests) through the
# approved Microsoft PyPI feed proxy. `python -m build` spins up its own isolated
# environment and pip-installs the build backend (pdm-backend) on every run; that
# isolated pip honors PIP_INDEX_URL. Without this it targets public PyPI, which is
# blocked/SSL-inspected on Microsoft-managed devices (CISO Central Feed Services
# policy) and injects network variability into build time.
export PIP_INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"
log "-- Set PIP_INDEX_URL for build isolation: $PIP_INDEX_URL"

log "-- fast_api build started"

# Redirect output to a per-phase log so it is preserved in the results share.
# Without redirection, stdout goes only to the RPC buffer and is lost on timeout.
BUILD_LOG="$LOG_DIR/mac_fast_api_build.log"
log "-- Build output: $BUILD_LOG"
/usr/bin/time -p -o "$LOG_DIR/mac_fast_api_build_time.log" "$VENV_PYTHON" -m build > "$BUILD_LOG" 2>&1
check_status "Building Fast API"

# Parse build phase timing
parse_time_output "$LOG_DIR/mac_fast_api_build_time.log" "build"

log "-- fast_api build ended"

log "-- fast_api tests started"

TEST_LOG="$LOG_DIR/mac_fast_api_test.log"
log "-- Test output: $TEST_LOG"
export PYTHONPATH="./docs_src"
/usr/bin/time -p -o "$LOG_DIR/mac_fast_api_test_time.log" "$VENV_PYTHON" -m pytest -n "$WORKERS" --dist loadgroup --cov --cov-context=test --cov-report=term tests scripts/tests > "$TEST_LOG" 2>&1
check_status "Running Fast API tests"

# Parse test phase timing
parse_time_output "$LOG_DIR/mac_fast_api_test_time.log" "test"

log "-- fast_api tests completed"

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
# Use real (wall clock) time for scenario_runtime as it represents actual elapsed time
scenario_runtime=$(echo "$build_real + $test_real" | bc)

log ""
log "========================================"
log "Fast API Metrics Summary"
log "========================================"
log "Build Phase: real=${build_real}s, user=${build_user}s, sys=${build_sys}s, cputime=${build_cputime}s"
log "Test Phase:  real=${test_real}s, user=${test_user}s, sys=${test_sys}s, cputime=${test_cputime}s"
log "scenario_runtime (total real time): ${scenario_runtime}s"
log "========================================"

# Write metrics CSV file (key,value format)
cat > "$METRICS_FILE" << EOF
scenario_runtime,$scenario_runtime
build_real,$build_real
build_user,$build_user
build_sys,$build_sys
build_cputime,$build_cputime
test_real,$test_real
test_user,$test_user
test_sys,$test_sys
test_cputime,$test_cputime
EOF

log "✓ Metrics saved to: $METRICS_FILE"

exit 0