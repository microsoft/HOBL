#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Shared by prep and run. Never replace Homebrew/system Node used by other workloads.
VSCODE_NODE_VERSION="26.9.0"
VSCODE_NODE_ARCHIVE="node-v${VSCODE_NODE_VERSION}-darwin-arm64"
VSCODE_NODE_ROOT="$BIN_DIR/mac_vscode_resources/nodejs"
VSCODE_NODE_DIR="$VSCODE_NODE_ROOT/$VSCODE_NODE_ARCHIVE"
# https://nodejs.org/dist/v26.9.0/SHASUMS256.txt
VSCODE_NODE_SHA256="6f3de7ed853ee283b4bf24b6e426618f1d357401ce5815db1866eb85eb4b05d9"

vscode_install_node() {
    if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
        log " ERROR - VS Code Node.js setup requires macOS ARM64"
        return 1
    fi
    if [ ! -x "$VSCODE_NODE_DIR/bin/node" ]; then
        node_tmp=$(mktemp -d "${TMPDIR:-/tmp}/hobl-vscode-node.XXXXXX") || return 1
        log "-- Downloading scenario-local Node.js $VSCODE_NODE_VERSION (arm64)"
        if ! curl -fL "https://nodejs.org/dist/v${VSCODE_NODE_VERSION}/${VSCODE_NODE_ARCHIVE}.tar.gz" -o "$node_tmp/node.tar.gz" ||
            ! echo "$VSCODE_NODE_SHA256  $node_tmp/node.tar.gz" | shasum -a 256 -c -; then
            log " ERROR - Node.js download or checksum verification failed"
            rm -rf "$node_tmp"
            return 1
        fi
        if ! mkdir -p "$VSCODE_NODE_ROOT" || ! tar -xzf "$node_tmp/node.tar.gz" -C "$VSCODE_NODE_ROOT"; then
            log " ERROR - Node.js extraction failed"
            rm -rf "$node_tmp"
            return 1
        fi
        rm -rf "$node_tmp"
    fi
    vscode_use_node
}

vscode_use_node() {
    if [ ! -x "$VSCODE_NODE_DIR/bin/node" ] || [ ! -x "$VSCODE_NODE_DIR/bin/npm" ]; then
        log " ERROR - Scenario-local Node.js is missing at $VSCODE_NODE_DIR. Re-run VS Code prep."
        return 1
    fi
    if [ "$("$VSCODE_NODE_DIR/bin/node" --version)" != "v$VSCODE_NODE_VERSION" ] ||
        [ "$("$VSCODE_NODE_DIR/bin/node" -p process.arch)" != "arm64" ]; then
        log " ERROR - Expected Node.js v$VSCODE_NODE_VERSION (arm64). Re-run VS Code prep."
        return 1
    fi
    export PATH="$VSCODE_NODE_DIR/bin:$PATH"
    hash -r
    log "-- Using scenario-local Node.js $(node --version): $VSCODE_NODE_DIR/bin/node"
    node_npm_version=$(npm --version) || return 1
    log "-- Using bundled npm $node_npm_version"
}