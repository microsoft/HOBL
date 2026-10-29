#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="/Users/Shared/hobl_bin"
export SUDO_ASKPASS=$BIN_DIR/get_password.sh
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_procyon_prep.log"

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

log "-- mac_procyon prep started"

if [ "$#" -ne 1 ]; then
    log "Usage: $0 [license_key]"
    exit 1
fi

# Installing Rosetta 2
log "-- Installing Rosetta 2"
if /usr/bin/pgrep -q oahd; then
    log "✓ Rosetta 2 already installed"
else
    sudo -A softwareupdate --install-rosetta --agree-to-license
    check_status "Rosetta 2 installation"
fi

for pkg in "$SCRIPT_DIR"/*.pkg; do
    pkg_name="$(basename "$pkg")"
    log "-- Installing: $pkg_name"
    sudo -A installer -pkg "$pkg" -target /
    check_status "$pkg_name installation"
done

LICENSE_KEY="$1"

find "/Library/UL/Procyon" -type f -name "UL_Procyon" -print0 |
while IFS= read -r -d '' procyon; do
    dir=$(dirname "$procyon")
    base_dir=$(basename "$dir")

    log "-- Registering: $base_dir"

    (
        cd "$dir" || exit 1
        ./UL_Procyon --register="$LICENSE_KEY"
    )

    check_status "$base_dir registration"
done

log "-- mac_procyon prep completed successfully"
exit 0
