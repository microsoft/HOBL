#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_procyon_run.log"

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

log "-- mac_procyon run started"

if [ "$#" -ne 2 ]; then
    log "Usage: $0 [definition_file] [output_xml_path]"
    exit 1
fi

def=$1
def_file=$(find "/Library/UL/Procyon" -type f -name "$def" -print -quit)

if [ -n "$def_file" ]; then
    dir=$(dirname "$def_file")
    base_dir=$(basename "$dir")

    log "-- Running $base_dir/$def"

    (
        cd "$dir" || exit 1
        ./UL_Procyon --definition="$def" --loop=1 --export-xml="$2"
    )

    check_status "$base_dir/$def run"
fi


log "-- mac_procyon run completed successfully"
exit 0
