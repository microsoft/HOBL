#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
phase=$1
workload=$2
scenario=$3
work_root=$4
data_dir=$5
toolchain=${6:-1.100.0}
jobs=${7:-0}
sample=${8:-1}
python_exe=${9:-}
repository=${10:-}
case "$scenario" in
    rust_analyzer_build|nushell_build|mac_rust_analyzer_build|mac_nushell_build) ;;
    *) printf ' ERROR - Invalid scenario name.\n' >&2; exit 1 ;;
esac
if [ "$(uname -s)" != Darwin ]; then
    printf ' ERROR - This launcher requires macOS; use invoke.ps1 on Windows.\n' >&2
    exit 1
fi
venv="$script_dir/.venvs/$scenario"
if [ "$phase" = prep ] && [ ! -x "$venv/bin/python" ]; then
    if [ -z "$python_exe" ]; then
        if ! command -v pyenv >/dev/null 2>&1; then
            printf ' ERROR - Install HOBL pyenv first, or supply Python explicitly for standalone validation.\n' >&2
            exit 1
        fi
        if ! pyenv versions --bare | grep -qx '3.12.10'; then
            pyenv install 3.12.10
        fi
        python_exe=$(PYENV_VERSION=3.12.10 pyenv which python)
    fi
    printf 'Python: %s\n' "$python_exe"
    "$python_exe" -m venv --without-pip "$venv"
fi
if [ ! -x "$venv/bin/python" ]; then
    printf ' ERROR - Scenario Python environment missing; re-run prep.\n' >&2
    exit 1
fi
"$venv/bin/python" -c 'import json, subprocess, tomllib; import sys; assert sys.version_info >= (3, 11)'
set -- "$script_dir/build.py" "$phase" --workload "$workload" --scenario "$scenario" \
    --work-root "$work_root" --data-dir "$data_dir" --toolchain "$toolchain" \
    --jobs "$jobs" --sample "$sample"
if [ -n "$repository" ]; then
    set -- "$@" --repository "$repository"
fi
exec "$venv/bin/python" "$@"
