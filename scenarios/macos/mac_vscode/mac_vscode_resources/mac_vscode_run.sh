#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

LOG_DIR="/Users/Shared/hobl_data"
METRICS_FILE="$LOG_DIR/mac_vscode_results.csv"
BIN_DIR="/Users/Shared/hobl_bin"
VSCODE_DIR="$BIN_DIR/vscode"
LOG_FILE="$LOG_DIR/mac_vscode_run.log"

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
# Args: $1 = time log file, $2 = phase name prefix (e.g., "build")
# Sets: <prefix>_real, <prefix>_user, <prefix>_sys, <prefix>_cputime
#
# Time metrics explained:
#   Real - Wall clock time from start to finish of the call.
#   User - CPU time spent in user-mode code within the process.
#   Sys  - CPU time spent in the kernel within the process.
#   User+Sys (cputime) - How much actual CPU time your process used.
#
parse_time_output() {
    local time_file="$1"
    local prefix="$2"
    
    if [ ! -f "$time_file" ]; then
        log " ERROR - Time log file not found: $time_file"
        return 1
    fi
    
    local real_val=$(grep "^real" "$time_file" | awk '{print $2}')
    local user_val=$(grep "^user" "$time_file" | awk '{print $2}')
    local sys_val=$(grep "^sys" "$time_file" | awk '{print $2}')
    local cputime=$(echo "$user_val + $sys_val" | bc)
    
    eval "${prefix}_real=$real_val"
    eval "${prefix}_user=$user_val"
    eval "${prefix}_sys=$sys_val"
    eval "${prefix}_cputime=$cputime"
    
    log "✓ Parsed $prefix phase: real=${real_val}s, user=${user_val}s, sys=${sys_val}s, cputime=${cputime}s"
}

echo "-- mac_vscode_run.sh started $(date)" > "$LOG_FILE"
log "-- vscode run started"

# Source profile
if [ -f ~/.zprofile ]; then
    source ~/.zprofile
    check_status "Loading profile"
else
    echo " ERROR - ~/.zprofile not found"
    exit 1
fi

# Use the prep-installed runtime, not a different Node selected by the profile.
. "$BIN_DIR/mac_vscode_resources/mac_vscode_node.sh" || exit 1
vscode_use_node || exit 1

# Verify required commands are available
log "-- Verifying required commands"
check_command "node" || exit 1
check_command "npm" || exit 1
check_command "python" || exit 1

log "-- Node.js version: $(node --version)"
log "-- npm version: $(npm --version)"
log "-- Python version: $(python --version 2>&1)"

# Verify VS Code directory exists
if [ ! -d "$VSCODE_DIR" ]; then
    log " ERROR - VS Code directory not found: $VSCODE_DIR"
    log "Please run mac_vscode_prep.sh first"
    exit 1
fi

log "-- Changing directory to: $VSCODE_DIR"
cd "$VSCODE_DIR" || { log " ERROR - Failed to change to $VSCODE_DIR"; exit 1; }

# Verify we're in a git repository
if [ ! -d ".git" ]; then
    log " ERROR - Not a git repository: $VSCODE_DIR"
    exit 1
fi
log "✓ Current directory: $(pwd)"

# Clean previous build outputs (keep node_modules)
log "-- Cleaning previous build outputs"
rm -rf .build
rm -rf out
log "✓ Cleaned .build and out directories"

# Build VS Code
log "-- Starting VS Code compilation"

# Redirect npm output to a per-phase log so it is preserved in the results
# share. Without redirection, stdout goes only to the RPC buffer and is lost
# on timeout.
BUILD_LOG="$LOG_DIR/mac_vscode_build.log"
log "-- Build output: $BUILD_LOG"

/usr/bin/time -p -o "$LOG_DIR/mac_vscode_build_time.log" npm run compile > "$BUILD_LOG" 2>&1
check_status "VS Code build"

parse_time_output "$LOG_DIR/mac_vscode_build_time.log" "build"

log "-- vscode build ended"

scenario_runtime=$build_real

log ""
log "========================================"
log "VS Code Build Metrics Summary"
log "========================================"
log "Build Phase: real=${build_real}s, user=${build_user}s, sys=${build_sys}s, cputime=${build_cputime}s"
log "scenario_runtime (total real time): ${scenario_runtime}s"
log "========================================"

cat > "$METRICS_FILE" << EOF
scenario_runtime,$scenario_runtime
build_real,$build_real
build_user,$build_user
build_sys,$build_sys
build_cputime,$build_cputime
EOF

log "✓ Metrics saved to: $METRICS_FILE"

exit 0
