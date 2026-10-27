#!/usr/bin/env bash
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

set -eo pipefail
export LC_ALL=C

PreRun=false
PostRun=false
LogFile="Config"
OverrideString=""
pre_run_file=""

for arg in "$@"; do
    case $arg in
        --prerun) PreRun=true ;;
        --postrun) PostRun=true ;;
        --logfile=*) LogFile="${arg#*=}" ;;
        --prerunfile=*) pre_run_file="${arg#*=}" ;;
        --override-string=*) OverrideString="${arg#*=}" ;;
        *)
            echo " ERROR - Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

if $PreRun && $PostRun; then
    echo " ERROR - Specify only one of --prerun and --postrun." >&2
    exit 1
fi

declare -A Table
declare -A OverrideTable
declare -a Keys=()

add_to_table() {
    local key="$1"
    if [[ ! -v Table["$key"] ]]; then
        Keys+=("$key")
    fi
    Table["$key"]="$2"
}

csv_field() {
    local value="$1"
    if [[ "$value" == *[,$'\r\n\"']* ]]; then
        value=${value//\"/\"\"}
        printf '"%s"' "$value"
    else
        printf '%s' "$value"
    fi
}

output_table() {
    local key value output_file="${LogFile}.csv"
    : > "$output_file"
    for key in "${Keys[@]}"; do
        value="${OverrideTable[$key]-${Table[$key]}}"
        {
            csv_field "$key"
            printf ','
            csv_field "$value"
            printf '\n'
        } | tee -a "$output_file"
    done
    echo "Configuration table saved to $output_file"
}

# Preserve the existing flat override format, including HOBL's single-quoted keys.
# Nested objects/arrays and commas within values are not supported.
json_to_override_table() {
    local json_string="$1" pair key value
    local -a pairs
    [[ -n "$json_string" ]] || return 0
    json_string=${json_string//[\{\}]/}
    json_string=${json_string//[\[\]]/}
    json_string=${json_string//\'/}
    json_string=${json_string//\"/}
    IFS=',' read -r -a pairs <<< "$json_string"
    for pair in "${pairs[@]}"; do
        if [[ "$pair" != *:* ]]; then
            echo " ERROR - Invalid override pair: $pair" >&2
            exit 1
        fi
        key=$(printf '%s' "${pair%%:*}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        value=$(printf '%s' "${pair#*:}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [[ -z "$key" ]]; then
            echo " ERROR - Override keys cannot be empty." >&2
            exit 1
        fi
        add_to_table "$key" "$value"
        OverrideTable["$key"]="$value"
    done
}

read_attribute() {
    if [[ -r "$1" ]]; then
        cat "$1"
    else
        printf 'N/A'
    fi
}

is_number() {
    [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

add_reading() {
    if [[ -z "$2" || "$2" == "N/A" ]]; then
        echo " WARNING - $1 unavailable on this system." >&2
        add_to_table "$1" "N/A"
    else
        add_to_table "$1" "$2"
    fi
}

read_battery() {
    local supply current full voltage
    battery_level="N/A"
    battery_status="N/A"
    battery_capacity_wh="N/A"
    for supply in /sys/class/power_supply/*; do
        [[ "$(read_attribute "$supply/type")" == "Battery" ]] || continue
        [[ "$(read_attribute "$supply/present")" != "0" ]] || continue
        battery_status=$(read_attribute "$supply/status")
        battery_status=${battery_status,,}
        [[ "$battery_status" != "full" ]] || battery_status="charged"
        current=$(read_attribute "$supply/energy_now")
        full=$(read_attribute "$supply/energy_full")
        if ! is_number "$current" || ! is_number "$full" || [[ "$full" == "0" ]]; then
            current=$(read_attribute "$supply/charge_now")
            full=$(read_attribute "$supply/charge_full")
        fi
        if is_number "$current" && is_number "$full" && [[ "$full" != "0" ]]; then
            battery_level=$(awk -v now="$current" -v full="$full" 'BEGIN {printf "%.2f", now / full * 100}')
        else
            battery_level=$(read_attribute "$supply/capacity")
            is_number "$battery_level" || battery_level="N/A"
        fi
        full=$(read_attribute "$supply/energy_full")
        if is_number "$full" && [[ "$full" != "0" ]]; then
            battery_capacity_wh=$(awk -v full="$full" 'BEGIN {print full / 1000000}')
        else
            full=$(read_attribute "$supply/charge_full")
            voltage=$(read_attribute "$supply/voltage_min_design")
            if is_number "$full" && is_number "$voltage" && [[ "$full" != "0" && "$voltage" != "0" ]]; then
                battery_capacity_wh=$(awk -v full="$full" -v volts="$voltage" 'BEGIN {print full * volts / 1e12}')
            fi
        fi
        # Match the original single-battery readings; do not mix different batteries.
        break
    done
}

read_brightness() {
    local display current maximum
    screen_brightness_pct="N/A"
    for display in /sys/class/backlight/*; do
        current=$(read_attribute "$display/brightness")
        maximum=$(read_attribute "$display/max_brightness")
        if is_number "$current" && is_number "$maximum" && [[ "$maximum" != "0" ]]; then
            screen_brightness_pct=$(awk -v now="$current" -v max="$maximum" 'BEGIN {printf "%.0f", now / max * 100}')
            break
        fi
    done
}

read_volume() {
    local output
    audio_volume="N/A"
    if command -v wpctl >/dev/null 2>&1; then
        if output=$(wpctl get-volume @DEFAULT_AUDIO_SINK@); then
            audio_volume=$(awk '/^Volume: [0-9.]+/ {printf "%.0f", $2 * 100}' <<< "$output")
            return
        fi
        echo " WARNING - wpctl could not read the default audio sink; trying pactl." >&2
    fi
    if command -v pactl >/dev/null 2>&1; then
        if output=$(pactl get-sink-volume @DEFAULT_SINK@); then
            audio_volume=$(awk 'match($0, /[0-9]+%/) {print substr($0, RSTART, RLENGTH - 1); exit}' <<< "$output")
        else
            echo " WARNING - pactl could not read the default audio sink." >&2
        fi
    fi
}

collect_run_readings() {
    local phase="$1"
    read_battery
    read_brightness
    read_volume
    add_reading "Run $phase Battery State (%)" "$battery_level"
    add_reading "Run $phase Charge State" "$battery_status"
    add_reading "Run $phase Screen Brightness (%)" "$screen_brightness_pct"
    add_reading "Run $phase Audio Volume (%)" "$audio_volume"
}

json_to_override_table "$OverrideString"

if $PreRun; then
    echo "Running pre-run checks..."
    add_to_table "Run Start Time" "$(date +'%Y-%m-%d %H:%M:%S')"
    collect_run_readings "Start"
elif $PostRun; then
    if [[ ! -f "$pre_run_file" ]]; then
        echo " ERROR - Pre-run file $pre_run_file not found." >&2
        exit 1
    fi
    run_start_time=$(awk -F, '$1 == "Run Start Time" {sub(/\r$/, "", $2); print $2; exit}' "$pre_run_file")
    if [[ -z "$run_start_time" ]] || ! stime=$(date -d "$run_start_time" +%s); then
        echo " ERROR - Missing or invalid Run Start Time in pre-run file." >&2
        exit 1
    fi
    echo "Running post-run checks..."
    run_stop_time=$(date +'%Y-%m-%d %H:%M:%S')
    etime=$(date -d "$run_stop_time" +%s)
    run_duration_seconds=$((etime - stime))
    if ((run_duration_seconds < 0)); then
        echo " ERROR - Run Stop Time precedes Run Start Time." >&2
        exit 1
    fi
    add_to_table "Run Stop Time" "$run_stop_time"
    collect_run_readings "Stop"
    add_to_table "Run Duration (min)" "$(awk -v seconds="$run_duration_seconds" 'BEGIN {printf "%.2f", seconds / 60}')"
    start_battery_level=$(awk -F, '$1 == "Run Start Battery State (%)" {sub(/\r$/, "", $2); print $2; exit}' "$pre_run_file")
    battery_drain_percentage="N/A"
    battery_drain_wh="N/A"
    battery_drain_rate_mw="N/A"
    if is_number "$start_battery_level" && is_number "$battery_level"; then
        battery_drain_percentage=$(awk -v start="$start_battery_level" -v stop="$battery_level" 'BEGIN {drain = start - stop; printf "%.2f", (drain > 0 ? drain : 0)}')
        if is_number "$battery_capacity_wh"; then
            battery_drain_wh=$(awk -v capacity="$battery_capacity_wh" -v drain="$battery_drain_percentage" 'BEGIN {printf "%.2f", capacity * drain / 100}')
            if ((run_duration_seconds > 0)); then
                battery_drain_rate_mw=$(awk -v capacity="$battery_capacity_wh" -v drain="$battery_drain_percentage" -v seconds="$run_duration_seconds" 'BEGIN {printf "%.0f", capacity * drain / 100 * 1000 * 3600 / seconds}')
            fi
        fi
    fi
    add_reading "Battery Drain (%)" "$battery_drain_percentage"
    add_reading "Battery Drain (Wh)" "$battery_drain_wh"
    add_reading "Run Drain Rate (mW)" "$battery_drain_rate_mw"
else
    processor_model=$(awk -F: '/^(model name|Model|Hardware)[[:space:]]*:/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' /proc/cpuinfo)
    if [[ -z "$processor_model" ]] && command -v lscpu >/dev/null 2>&1; then
        processor_model=$(lscpu | sed -n 's/^Model name:[[:space:]]*//p')
    fi
    add_reading "CPU Name" "$processor_model"
    add_to_table "CPU Architecture" "$(uname -m)"
    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        add_to_table "OS Version" "${PRETTY_NAME:-${VERSION_ID:-N/A}}"
    else
        add_reading "OS Version" "N/A"
    fi
    add_to_table "OS Build Version" "$(uname -r)"
    add_reading "Serial Number" "$(read_attribute /sys/class/dmi/id/product_serial)"
    system_model_identifier=$(read_attribute /sys/class/dmi/id/product_name)
    if [[ "$system_model_identifier" == "N/A" && -r /sys/firmware/devicetree/base/model ]]; then
        system_model_identifier=$(tr -d '\0' < /sys/firmware/devicetree/base/model)
    fi
    add_reading "Model Identifier" "${system_model_identifier//,/_}"
    add_reading "Memory Size (GB)" "$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') * 1024 / 1000000000 ))"
    add_reading "Storage Size (GB)" "$(df -B1 --output=size / | awk 'NR == 2 {printf "%.0f", $1 / 1000000000}')"
fi

output_table
