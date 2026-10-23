#!/bin/bash

usage() {
    echo "Usage: $0 [-c]"
    echo "  -c: Clean build directory before starting"
    exit 1
}

ARCH="macos"
CLEAN_BUILD=0

while getopts "c" opt; do
    case "$opt" in
        c)
            CLEAN_BUILD=1
            ;;
        *)
            usage
            ;;
    esac
done

if [ "$ARCH" != "macos" ]; then
    echo "Error: Unsupported architecture: $ARCH"
    usage
fi

echo "Building for architecture: $ARCH"

BUILD_DIR="build_${ARCH}"

if [ $CLEAN_BUILD -eq 1 ]; then
    echo "Cleaning build directory..."
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || { echo "Failed to change directory to $BUILD_DIR"; exit 1; }

if [ $CLEAN_BUILD -eq 1 ]; then
    cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="../install_macos"
fi

cmake --build . --config Release

cd ..
