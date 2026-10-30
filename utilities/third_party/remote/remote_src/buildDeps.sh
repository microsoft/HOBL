#!/bin/bash

usage() {
    echo "Usage: $0 -a <arch>"
    echo "  -a: Target architecture. Supported values: x64, ARM64, macos (default: x64)"
    exit 1
}

ARCH="x64"

while getopts "a:" opt; do
    case ${opt} in
        a)
            ARCH=${OPTARG}
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

if [ "$ARCH" == "macos" ]; then
    brew install libpng jpeg-turbo
    exit
fi

DEPS_DIR="deps"
mkdir -p "$DEPS_DIR"
cd "$DEPS_DIR" || { echo "Failed to change directory to $DEPS_DIR"; exit 1; }

download_and_extract() {
    local url="$1"
    local tar_name="$2"
    local dir_name="$3"

    if [ ! -d "$dir_name" ]; then
        echo "Downloading $dir_name..."
        curl -fsSL -o "$tar_name" "$url"
        echo "Extracting $tar_name..."
        tar -xzf "$tar_name"
        sleep 20

        # Assumes the tarball contains a single top-level directory
        extracted_dir=$(tar -tf "$tar_name" | head -1 | cut -f1 -d"/")
        mv "$extracted_dir" "$dir_name"
        rm "$tar_name"
    else
        echo "$dir_name already exists. Skipping download"
    fi
}

download_and_extract "https://github.com/madler/zlib/archive/v1.3.1.tar.gz" "zlib.tar.gz" "zlib"
download_and_extract "https://github.com/libjpeg-turbo/libjpeg-turbo/archive/3.1.0.tar.gz" "libjpeg.tar.gz" "libjpeg"
download_and_extract "http://prdownloads.sourceforge.net/libpng/libpng-1.6.47.tar.gz?download" "libpng.tar.gz" "libpng"

configure_and_build() {
    local dep_dir="$1"
    shift
    local cmake_args=("$@")

    echo "Configuring and building $dep_dir..."
    pushd "$dep_dir" > /dev/null || exit 1

    BUILD_DIR="build_${ARCH}"
    rm -rf "$BUILD_DIR"
    mkdir "$BUILD_DIR"
    pushd "$BUILD_DIR" > /dev/null || exit 1

    cmake .. -A "$ARCH" -DCMAKE_BUILD_TYPE=Release "${cmake_args[@]}"
    cmake --build . --config Release

    popd > /dev/null
    popd > /dev/null
}

configure_and_build "zlib"

if [ "$ARCH" == "ARM64" ]; then
    configure_and_build "libjpeg" -DCMAKE_TOOLCHAIN_FILE=../../libjpeg_toolchain.cmake -DWITH_CRT_DLL=ON
else
    configure_and_build "libjpeg" -DCMAKE_ASM_NASM_COMPILER="/c/Program Files/NASM/nasm.exe" -DWITH_CRT_DLL=ON
fi

configure_and_build "libpng" -DZLIB_INCLUDE_DIR="../../zlib;../../zlib/build_${ARCH}" -DZLIB_LIBRARY=../../zlib/build_${ARCH}/Release/zlibstatic.lib

cp zlib/build_${ARCH}/zconf.h zlib
cp libjpeg/build_${ARCH}/jconfig.h libjpeg/src
cp libpng/build_${ARCH}/pnglibconf.h libpng

echo "All dependencies have been built for architecture $ARCH"
