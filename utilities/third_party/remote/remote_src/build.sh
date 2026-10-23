#!/bin/bash

usage() {
    echo "Usage: $0 -a <arch> [-c]"
    echo "  -a: Target architecture. Supported values: x64, ARM64, macos (default: x64)"
    echo "  -c: Clean build directory before starting"
    exit 1
}

ARCH="x64"
CLEAN_BUILD=0

while getopts "a:c" opt; do
    case "$opt" in
        a)
            ARCH="$OPTARG"
            ;;
        c)
            CLEAN_BUILD=1
            ;;
        *)
            usage
            ;;
    esac
done

if [ "$ARCH" != "x64" ] && [ "$ARCH" != "ARM64" ] && [ "$ARCH" != "macos" ]; then
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

if [ "$ARCH" == "macos" ]; then
    JPEG_INCLUDE_DIR="/opt/homebrew/opt/jpeg-turbo/include"

    if [ $CLEAN_BUILD -eq 1 ]; then
        INSTALL_DIR="../install_macos"

        echo "Cleaning install directory..."
        rm -rf "$INSTALL_DIR"

        cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
        -DBUILD_SHARED_LIBS=OFF \
        -DJPEG_INCLUDE_DIR="$JPEG_INCLUDE_DIR" 
    fi

    cmake --build . --config Release
    cmake --install . --config Release

    cd ..
    exit
fi

ZLIB_INCLUDE_DIR="../deps/zlib"
ZLIB_LIBRARY="../deps/zlib/build_${ARCH}/Release/zlibstatic"

JPEG_INCLUDE_DIR="../deps/libjpeg/src"
JPEG_LIBRARY="../deps/libjpeg/build_${ARCH}/Release/turbojpeg-static"

PNG_INCLUDE_DIR="../deps/libpng"
PNG_LIBRARY="../deps/libpng/build_${ARCH}/Release/libpng16_static"

if [ $CLEAN_BUILD -eq 1 ]; then
    cmake .. \
    -A "$ARCH" \
    -DCMAKE_BUILD_TYPE=Release \
    -DZLIB_INCLUDE_DIR="$ZLIB_INCLUDE_DIR" \
    -DZLIB_LIBRARY="$ZLIB_LIBRARY" \
    -DJPEG_INCLUDE_DIR="$JPEG_INCLUDE_DIR" \
    -DJPEG_LIBRARY="$JPEG_LIBRARY" \
    -DPNG_PNG_INCLUDE_DIR="$PNG_INCLUDE_DIR" \
    -DPNG_LIBRARY="$PNG_LIBRARY"
fi

cmake --build . --config Release

cd ..
