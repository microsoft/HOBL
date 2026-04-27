#!/bin/zsh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

zmodload zsh/datetime

PreRun=false
PostRun=false
LogFile="Config"
OverrideString=""
BattCapacity=53 # Wh

# Parse command line arguments
for arg in "$@"; do
    case $arg in
        --prerun)
            PreRun=true
            ;;
        --postrun)
            PostRun=true
            ;;
        --logfile=*)
            LogFile="${arg#*=}"
            ;;
        --prerunfile=*)
            pre_run_file="${arg#*=}"
            ;;
        --override-string=*)
            OverrideString="${arg#*=}"
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done    

# Initialize a table, Table, to store the configuration
declare -A Table
declare -A OverrideTable
declare -a Keys

# Function to add a key-value pair to the table
add_to_table() {
    local key="$1"
    local value="$2"
    Table[$key]=$value
    # if the key is not already in Keys, add it
    if [[ ! " ${Keys[@]} " =~ " ${key} " ]]; then   
        Keys+=($key)
    fi
}

# Function to print the table to a csv file
output_table() {
    local output_file="${LogFile}.csv"
    # Create output_file
    if [ -f "$output_file" ]; then
        rm "$output_file"
    fi
    # Write key-value pairs to the output file
    for key in "${Keys[@]}"; do
        # Check if the key exists in the OverrideTable
        if [[ -v OverrideTable["${key}"] ]]; then
            # If it exists, write the key and value to the output file
            echo "$key,${OverrideTable[$key]}"
            echo "$key,${OverrideTable[$key]}" >> "$output_file"
        else
            # If it does not exist, use the value from Table
            echo "$key,${Table[$key]}"
            echo "$key,${Table[$key]}" >> "$output_file"
        fi
    done
    echo "Configuration table saved to $output_file"
}

# Function to convert json string to associative array using zsh's built-in json parser
# Note: This function assumes that the input JSON is well-formed and does not contain nested objects or arrays.
# Usage: json_to_table '{"key1":"value1", "key2":"value2"}'
json_to_override_table() {
    local json_string="$1"
    # Remove curly braces and quotes
    json_string=${json_string//[{}]/}
    json_string=${json_string//[\[\]]/}
    json_string=${json_string//\'/}
    json_string=${json_string//\"/}
    # Convert to associative array
    for pair in ${(s:,:)json_string}; do
        key=${pair%%:*}  # Extract key
        # strip key of leading whitespace
        key=$(echo $key | sed -e 's/^[[:space:]]*//')
        value=${pair#*:} # Extract value
        # strip value of leading whitespace
        value=$(echo $value | sed -e 's/^[[:space:]]*//')
        # echo "Setting key: $key, value: $value"
        OverrideTable[$key]=$value
        Keys+=($key)
    done
    # Print OverrideTable for debugging
    # echo "OverrideTable contents:"
    # Iterate over the OverrideTable and print each key-value pair
    for key in "${(@k)OverrideTable}"; do
        value=${OverrideTable[$key]}
        # echo "Key: $key, Value: $value"
    done
}

# Parse overrides
json_to_override_table $OverrideString

# if PreRun is true, run the pre-run checks
if [ "$PreRun" = true ]; then
    echo "Running pre-run checks..."
    # add_to_table "Test Name" ""
    # add_to_table "Scenario" ""
    add_to_table "Run Start Time" "$(date +'%Y-%m-%d %H:%M:%S')"
    # Add current battery level without the percent sign
    # battery_level=$(pmset -g batt | grep -o '[0-9]\+%' | head -n 1 | tr -d '%')
    raw_current_capacity_level=$(ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawCurrentCapacity raw -)
    raw_max_capacity_level=$(ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawMaxCapacity raw -)
    battery_level=$(printf "%.2f" $(echo "$raw_current_capacity_level / $raw_max_capacity_level * 100" | bc -l))
    add_to_table "Run Start Battery State (%)" "$battery_level"
    battery_status=$(pmset -g batt | grep -o 'discharging\|charging\|charged' | head -n 1)
    add_to_table "Run Start Charge State" "$battery_status"
    # Add screen brightness
    screen_brightness=$(/Users/Shared/hobl_bin/brightness -l | grep 'brightness' | awk '{print $4}')
    screen_brightness_pct=$(echo "$screen_brightness * 100" | bc -l)
    screen_brightness_pct=$(printf "%.0f" $screen_brightness_pct) # round to nearest integer
    add_to_table "Run Start Screen Brightness (%)" "$screen_brightness_pct"
    # Add audio volume
    audio_volume=$(osascript -e "output volume of (get volume settings)")
    add_to_table "Run Start Audio Volume (%)" "$audio_volume"
# if PostRun is true, run the post-run checks
elif [ "$PostRun" = true ]; then
    # Read in PreRun csv file to get the Run Start Time
    if [ ! -f "$pre_run_file" ]; then
        echo " ERROR - Pre-run file $pre_run_file not found."
        exit 1
    fi
    # Read the Run Start Time from the pre-run file
    run_start_time=$(awk -F, '/Run Start Time/ {print $2}' "$pre_run_file")
    if [ -z "$run_start_time" ]; then
        echo " ERROR - Run Start Time not found in pre-run file."
        exit 1
    fi
    echo "Running post-run checks..."
    run_stop_time=$(date +'%Y-%m-%d %H:%M:%S')
    add_to_table "Run Stop Time" "$run_stop_time"
    # Add current battery level without the percent sign
    # battery_level=$(pmset -g batt | grep -o '[0-9]\+%' | head -n 1 | tr -d '%')
    raw_current_capacity_level=$(ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawCurrentCapacity raw -)
    raw_max_capacity_level=$(ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawMaxCapacity raw -)
    battery_level=$(printf "%.2f" $(echo "$raw_current_capacity_level / $raw_max_capacity_level * 100" | bc -l))
    add_to_table "Run Stop Battery State (%)" "$battery_level"
    battery_status=$(pmset -g batt | grep -o 'discharging\|charging\|charged' | head -n 1)
    add_to_table "Run Stop Charge State" "$battery_status"
    # Add screen brightness
    screen_brightness=$(/Users/Shared/hobl_bin/brightness -l | grep 'brightness' | awk '{print $4}')
    screen_brightness_pct=$(echo "$screen_brightness * 100" | bc -l)
    screen_brightness_pct=$(printf "%.0f" $screen_brightness_pct) # round to nearest integer
    add_to_table "Run Stop Screen Brightness (%)" "$screen_brightness_pct"
    # Add audio volume
    audio_volume=$(osascript -e "output volume of (get volume settings)")
    add_to_table "Run Stop Audio Volume (%)" "$audio_volume"
    # Calculate duration in seconds
    stime=$(strftime -r "%Y-%m-%d %H:%M:%S" "$run_start_time")
    etime=$(strftime -r "%Y-%m-%d %H:%M:%S" "$run_stop_time")
    if [[ -z "$stime" || -z "$etime" ]]; then
        echo " ERROR - Unable to calculate run duration. Invalid timestamps."
        exit 1
    fi
    run_duration_seconds=$(( etime - stime ))
    # echo "Run duration in seconds: $run_duration_seconds"
    # Convert duration to minutes
    run_duration_hours=$(( run_duration_seconds / 3600.0 ))
    run_duration_minutes=$(printf "%0.2f" $(( (run_duration_seconds) / 60.0 )))
    add_to_table "Run Duration (min)" "$run_duration_minutes"
    # add_to_table "Run Duration (hrs)" "$run_duration_hours"

    # Calculate battery drain percentage
    start_battery_level=$(awk -F, '/Run Start Battery State/ {print $2}' "$pre_run_file")
    # start_battery_level=90 # For testing purposes, set a fixed start battery level
    # echo "Start Battery Level from pre-run: $start_battery_level"
    battery_drain_percentage=$((start_battery_level - battery_level))
    if [ $battery_drain_percentage -lt 0 ]; then
        battery_drain_percentage=0
    fi
    add_to_table "Battery Drain (%)" "$battery_drain_percentage"
    # Calculate battery drain rate
    battery_drain_fraction=$(printf "%0.2f" $(echo "$battery_drain_percentage / 100.0" | bc -l))
    echo "Battery drain fraction: $battery_drain_fraction"
    # Calculate battery drain in Wh
    battery_drain_wh=$(printf "%0.2f" $(echo "$BattCapacity * $battery_drain_fraction" | bc -l))
    add_to_table "Battery Drain (Wh)" "$battery_drain_wh"
    # Calculate battery drain in mWh
    battery_drain_mwh=$(printf "%0.2f" $(echo "$battery_drain_wh * 1000.0" | bc -l))
    # Calculate battery drain rate in mW
    # Only calculate if run_duration_hours is greater than 0 to avoid division by zero
    if [ $(( $(echo "$battery_drain_mwh > 0.0" | bc) )) -eq 1 ]; then
        battery_drain_rate_mw=$(printf "%0.0f" $(echo "$battery_drain_mwh / $run_duration_hours" | bc -l))
        add_to_table "Run Drain Rate (mW)" "$battery_drain_rate_mw"
    else
        add_to_table "Run Drain Rate (mW)" "0"
    fi
else
    # Get processor model
    processor_model=$(sysctl -n machdep.cpu.brand_string)
    add_to_table "CPU Name" "$processor_model"
    # Get system architecture
    system_architecture=$(uname -m)
    add_to_table "CPU Architecture" "$system_architecture"
    # Get system version
    system_version=$(sw_vers -productVersion)
    add_to_table "OS Version" "$system_version"
    # Get system build version
    system_build_version=$(sw_vers -buildVersion)
    add_to_table "OS Build Version" "$system_build_version"
    # Get system serial number
    system_serial_number=$(system_profiler SPHardwareDataType | awk '/Serial Number/{print $4}')
    add_to_table "Serial Number" "$system_serial_number"
    # Get system model identifier
    system_model_identifier=$(sysctl -n hw.model)
    system_model_identifier=${system_model_identifier//,/_}
    add_to_table "Model Identifier" "$system_model_identifier"
    # Get system memory size
    system_memory_size=$(sysctl -n hw.memsize)
    # Convert memory size from bytes to gigabytes
    system_memory_size_gb=$(echo "scale=2; $system_memory_size / 1024 / 1024 / 1024" | bc)
    add_to_table "Memory Size (GB)" "$system_memory_size_gb"
    # Get system disk size
    system_disk_size=$(diskutil info / | awk '/Disk Size/{print $3}')
    add_to_table "Storage Size (GB)" "$system_disk_size"
fi

# call output_table to save the configuration
output_table
