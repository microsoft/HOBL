#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

LOG_DIR="/Users/Shared/hobl_data"
METRICS_FILE="$LOG_DIR/mac_net_aspire_results.csv"
LOG_FILE="$LOG_DIR/mac_net_aspire_run.log"

BINLOG_ENABLED=0
for arg in "$@"; do
    if [ "$arg" = "--binlog" ]; then
        BINLOG_ENABLED=1
    fi
done

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

echo "-- mac_net_aspire_run.sh started $(date)" > "$LOG_FILE"
log "-- net_aspire run started"

# Source profile
if [ -f ~/.zprofile ]; then
    source ~/.zprofile
    check_status "Loading profile"
else
    echo " ERROR - ~/.zprofile not found"
    exit 1
fi

# Set BIN_DIR to aspire repo
BIN_DIR="/Users/Shared/hobl_bin/aspire"

log "-- Changing directory to: $BIN_DIR"

# Change to aspire directory
if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - Aspire directory not found: $BIN_DIR"
    log "Please run mac_net_aspire_prep.sh first"
    exit 1
fi
log "✓ Aspire directory exists"

cd $BIN_DIR || {
    log " ERROR - Failed to change to $BIN_DIR"
    exit 1
}
log "✓ Current directory: $(pwd)"

# Verify build script exists
if [ ! -f "build.sh" ]; then
    log " ERROR - build.sh not found in $BIN_DIR"
    exit 1
fi
log "✓ build.sh found"

# Increase Playwright browser download timeout (default is too short for slow CDN)
export PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000
log "-- Set PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 (5 minutes)"

# ============================================================================
# Clean phase (not timed)
# ============================================================================
log "-- net_aspire clean started"
./build.sh --clean
check_status "Cleaning .NET Aspire"
log "-- net_aspire clean ended"

# ============================================================================
# Restore phase (not timed)
# ============================================================================
log "-- net_aspire restore started"
./build.sh --restore
check_status "Restoring .NET Aspire"
log "-- net_aspire restore ended"

# ============================================================================
# Build phase (timed)
# ============================================================================
set -- --build
if [ "$BINLOG_ENABLED" -eq 1 ]; then
    BINLOG_FILE="$LOG_DIR/mac_net_aspire_build_$(date +%Y%m%d_%H%M%S)_$$.binlog"
    set -- "$@" "/bl:$BINLOG_FILE"
    log "-- Binary logging enabled (adds build overhead): $BINLOG_FILE"
fi

log "-- net_aspire build started"

# Redirect output to a per-phase log so it is preserved in the results share.
# Without redirection, stdout goes only to the RPC buffer and is lost on timeout.
BUILD_LOG="$LOG_DIR/mac_net_aspire_build.log"
log "-- Build output: $BUILD_LOG"
/usr/bin/time -p -o "$LOG_DIR/mac_net_aspire_build_time.log" ./build.sh "$@" > "$BUILD_LOG" 2>&1
check_status "Building .NET Aspire"

# Parse build phase timing
parse_time_output "$LOG_DIR/mac_net_aspire_build_time.log" "build"

log "-- net_aspire build ended"

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
# Use real (wall clock) time for scenario_runtime as it represents actual elapsed time
scenario_runtime=$build_real

log ""
log "========================================"
log ".NET Aspire Metrics Summary"
log "========================================"
log "Build Phase: real=${build_real}s, user=${build_user}s, sys=${build_sys}s, cputime=${build_cputime}s"
log "scenario_runtime (total real time): ${scenario_runtime}s"
log "========================================"

# Write metrics CSV file (key,value format)
cat > "$METRICS_FILE" << EOF
scenario_runtime,$scenario_runtime
build_real,$build_real
build_user,$build_user
build_sys,$build_sys
build_cputime,$build_cputime
EOF

log "✓ Metrics saved to: $METRICS_FILE"

exit 0
