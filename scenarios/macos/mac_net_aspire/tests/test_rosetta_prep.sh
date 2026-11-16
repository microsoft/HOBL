#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Only the Rosetta prep block is executed; installers and architecture checks are mocked.
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
PREP_SCRIPT="$SCRIPT_DIR/../mac_net_aspire_resources/mac_net_aspire_prep.sh"
TEST_DIR=$(mktemp -d)
TEST_CASES="installed intel installed_now install_failed unusable installed_with_error"

cleanup() {
    for name in $TEST_CASES; do
        rm -f "$TEST_DIR/$name.ready" "$TEST_DIR/$name.trace" "$TEST_DIR/$name.log"
    done
    rm -f "$TEST_DIR/rosetta.sh"
    rmdir "$TEST_DIR"
}
trap cleanup EXIT

sed -n '/^log() {$/,/^}$/p; /^check_status() {$/,/^}$/p' "$PREP_SCRIPT" > "$TEST_DIR/rosetta.sh"
sed -n '/^# Installing Rosetta 2$/,/^cd \$BIN_DIR/ { /^cd \$BIN_DIR/!p; }' "$PREP_SCRIPT" >> "$TEST_DIR/rosetta.sh"

run_case() (
    name=$1
    architecture=$2
    available=$3
    install_rc=$4
    usable_after_install=$5
    LOG_FILE="$TEST_DIR/$name.log"
    : > "$TEST_DIR/$name.trace"
    if [ "$available" = 1 ]; then
        : > "$TEST_DIR/$name.ready"
    fi

    uname() {
        printf '%s\n' "$architecture"
    }

    arch() {
        printf 'arch %s\n' "$*" >> "$TEST_DIR/$name.trace"
        [ -f "$TEST_DIR/$name.ready" ]
    }

    sudo() {
        printf 'sudo %s\n' "$*" >> "$TEST_DIR/$name.trace"
        printf 'softwareupdate: installer stdout\n'
        printf 'softwareupdate: installer stderr\n' >&2
        if [ "$usable_after_install" = 1 ]; then
            : > "$TEST_DIR/$name.ready"
        fi
        return "$install_rc"
    }

    . "$TEST_DIR/rosetta.sh"
    log "PREP_CONTINUED"
)

fail() {
    printf ' ERROR - %s\n' "$1" >&2
    exit 1
}

check_case() {
    name=$1
    expected_rc=$6
    if output=$(run_case "$1" "$2" "$3" "$4" "$5" 2>&1); then
        actual_rc=0
    else
        actual_rc=$?
    fi
    if [ "$actual_rc" -ne "$expected_rc" ]; then
        printf '%s\n' "$output" >&2
        fail "$name: expected exit $expected_rc, got $actual_rc"
    fi
    if [ "$expected_rc" = 0 ]; then
        assert_logged "$name" "PREP_CONTINUED"
    elif grep -Fq "PREP_CONTINUED" "$TEST_DIR/$name.log"; then
        fail "$name: prep continued without usable Rosetta"
    fi
}

assert_logged() {
    grep -Fq -- "$2" "$TEST_DIR/$1.log" || fail "$1: missing log message: $2"
}

assert_no_install() {
    if grep -Fq "sudo " "$TEST_DIR/$1.trace"; then
        fail "$1: installer was called unnecessarily"
    fi
}

check_case installed arm64 1 0 0 0
assert_no_install installed
assert_logged installed "Rosetta 2 already available"

check_case intel x86_64 0 0 0 0
assert_no_install intel
[ ! -s "$TEST_DIR/intel.trace" ] || fail "intel: attempted Rosetta verification"

check_case installed_now arm64 0 0 1 0
assert_logged installed_now "Rosetta 2 verified"
grep -Fq "sudo -A /usr/sbin/softwareupdate --install-rosetta --agree-to-license" "$TEST_DIR/installed_now.trace" ||
    fail "installed_now: missing Rosetta install command"

check_case install_failed arm64 0 42 0 1
assert_logged install_failed "softwareupdate: installer stdout"
assert_logged install_failed "softwareupdate: installer stderr"
assert_logged install_failed "softwareupdate rc=42"
assert_logged install_failed " ERROR - Rosetta 2 is unavailable"

check_case unusable arm64 0 0 0 1
assert_logged unusable "softwareupdate rc=0"
assert_logged unusable " ERROR - Rosetta 2 is unavailable"

check_case installed_with_error arm64 0 42 1 0
assert_logged installed_with_error "Rosetta 2 verified (softwareupdate rc=42)"

printf 'All 6 Rosetta prep tests passed.\n'
