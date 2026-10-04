#!/bin/zsh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# AI Foundry Local prep script for macOS
# Installs the pinned Foundry Local SDK and publishes the workload app.

BIN_DIR="/Users/Shared/hobl_bin"
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_foundrylocal_prep.log"
FOUNDRY_VERSION="${1:-2.0.1}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_DIR="$SCRIPT_DIR/foundrylocal_app"
DOTNET_DIR="$APP_DIR/.dotnet"
DOTNET="$DOTNET_DIR/dotnet"
PACKAGE_DIR="$APP_DIR/packages"
PUBLISH_DIR="$APP_DIR/publish"
PROJECT_FILE="$APP_DIR/FoundryLocalWorkload.csproj"
NUGET_CONFIG="$APP_DIR/NuGet.config"
RUNTIME_IDENTIFIER="osx-arm64"

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

echo "-- Foundry Local prep started" > "$LOG_FILE"
log "-- Foundry Local prep started"

ARCH=$(uname -m)
log "Detected architecture: $ARCH"

if [ "$ARCH" != "arm64" ]; then
    log " ERROR - Foundry Local for macOS is only available for Apple Silicon (arm64)"
    log " ERROR - Current architecture: $ARCH"
    exit 1
fi

if [ ! -d "$BIN_DIR" ]; then
    log " ERROR - Directory $BIN_DIR does not exist"
    exit 1
fi

if [ ! -f "$PROJECT_FILE" ]; then
    log " ERROR - Foundry Local workload project not found: $PROJECT_FILE"
    exit 1
fi

log "Target Foundry SDK version: $FOUNDRY_VERSION"

# ============================================================================
# Step 1: Install a per-scenario .NET 8 SDK
# ============================================================================
log "Step 1: Installing per-scenario .NET 8 SDK..."

mkdir -p "$DOTNET_DIR"
if [ ! -x "$DOTNET" ]; then
    DOTNET_INSTALL="$APP_DIR/dotnet-install.sh"
    log "Downloading the official dotnet-install script..."
    /usr/bin/curl -fL --retry 3 https://dot.net/v1/dotnet-install.sh -o "$DOTNET_INSTALL"
    check $?
    chmod 700 "$DOTNET_INSTALL"

    log "Installing .NET 8 SDK to: $DOTNET_DIR"
    "$DOTNET_INSTALL" --channel 8.0 --architecture arm64 --install-dir "$DOTNET_DIR"
    check $?
    rm -f "$DOTNET_INSTALL"
else
    log "Using existing per-scenario dotnet installation: $DOTNET"
fi

if [ ! -x "$DOTNET" ]; then
    log " ERROR - dotnet executable not found after installation: $DOTNET"
    exit 1
fi

DOTNET_VERSION=$("$DOTNET" --version 2>&1)
check $?
log "Using dotnet SDK: $DOTNET_VERSION"

case "$DOTNET_VERSION" in
    8.*) ;;
    *)
        log " ERROR - Expected a .NET 8 SDK, found: $DOTNET_VERSION"
        exit 1
        ;;
esac

# ============================================================================
# Step 2: Download the Foundry Local 2.0.1 packages
# ============================================================================
log "Step 2: Downloading Foundry Local SDK version $FOUNDRY_VERSION..."

mkdir -p "$PACKAGE_DIR"
for PACKAGE in Microsoft.AI.Foundry.Local Microsoft.AI.Foundry.Local.Runtime; do
    PACKAGE_FILE="$PACKAGE_DIR/$PACKAGE.$FOUNDRY_VERSION.nupkg"
    PACKAGE_URL="https://www.nuget.org/api/v2/package/$PACKAGE/$FOUNDRY_VERSION"
    log "Downloading $PACKAGE $FOUNDRY_VERSION from: $PACKAGE_URL"
    /usr/bin/curl -fL --retry 3 "$PACKAGE_URL" -o "$PACKAGE_FILE"
    check $?

    if [ ! -s "$PACKAGE_FILE" ]; then
        log " ERROR - Downloaded package is missing or empty: $PACKAGE_FILE"
        exit 1
    fi
done

# ============================================================================
# Step 3: Restore and publish the workload app
# ============================================================================
log "Step 3: Publishing Foundry Local workload for $RUNTIME_IDENTIFIER..."

if [ -d "$PUBLISH_DIR" ]; then
    rm -rf "$PUBLISH_DIR"
fi
mkdir -p "$PUBLISH_DIR"

"$DOTNET" restore "$PROJECT_FILE" \
    --runtime "$RUNTIME_IDENTIFIER" \
    --configfile "$NUGET_CONFIG" 2>&1 | while IFS= read -r line; do log "  $line"; done
check ${pipestatus[1]}

"$DOTNET" publish "$PROJECT_FILE" \
    --configuration Release \
    --runtime "$RUNTIME_IDENTIFIER" \
    --self-contained false \
    --no-restore \
    --output "$PUBLISH_DIR" 2>&1 | while IFS= read -r line; do log "  $line"; done
check ${pipestatus[1]}

APP_DLL="$PUBLISH_DIR/FoundryLocalWorkload.dll"
if [ ! -f "$APP_DLL" ]; then
    log " ERROR - Published Foundry Local workload not found: $APP_DLL"
    exit 1
fi

log "Published workload: $APP_DLL"
log ""
log "========================================"
log "Foundry Local prep completed successfully"
log "SDK version: $FOUNDRY_VERSION"
log "Architecture: $ARCH"
log "========================================"
log "Log file: $LOG_FILE"

exit 0
