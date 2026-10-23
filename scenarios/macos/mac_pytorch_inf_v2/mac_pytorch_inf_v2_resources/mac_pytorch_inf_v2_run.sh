#!/bin/sh
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Set BIN_DIR to /Users/Shared/hobl_bin
BIN_DIR="/Users/Shared/hobl_bin"
LOG_DIR="/Users/Shared/hobl_data"
LOG_FILE="$LOG_DIR/mac_pytorch_inf_v2_run.log"
METRICS_FILE="$LOG_DIR/mac_pytorch_inf_v2_results.csv"
TIME_TRACE_FILE="$LOG_DIR/run_time.trace"
TOTAL_TOKEN_TRACE_FILE="$LOG_DIR/total_tokens.trace"
TPS_TRACE_FILE="$LOG_DIR/tokens_per_second.trace"
PYTHON_VERSION="3.14.8"

MODEL_TIER="portable"
LANE="eager"
QUANT="none"
SHAPE="short"
NO_GPU_FLAG=""

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --no-gpu) NO_GPU_FLAG="--no-gpu" ;;
        --model-tier) shift; MODEL_TIER="$1" ;;
        --lane) shift; LANE="$1" ;;
        --quant) shift; QUANT="$1" ;;
        --shape) shift; SHAPE="$1" ;;
    esac
    shift
done

START_TIME=$(date +%s)

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi

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

# Clear log file
echo "-- mac_pytorch_inf_v2 run started" > "$LOG_FILE"

log "-- mac_pytorch_inf_v2 run started (model_tier=$MODEL_TIER lane=$LANE quant=$QUANT shape=$SHAPE)"

# Detect architecture
ARCH=$(uname -m)
log "Detected architecture: $ARCH"

# Source profile to load brew + pyenv
log "-- Loading environment"
if [ -f ~/.zprofile ]; then
    source ~/.zprofile
else
    log " ERROR - ~/.zprofile not found"
    exit 1
fi

log "-- Setting Python version"
pyenv global "$PYTHON_VERSION"
if [ $? -ne 0 ]; then
    log " ERROR - Failed to set Python version $PYTHON_VERSION. Run prep script first."
    exit 1
fi

PYTHON_ACTIVE_VERSION=$(python --version 2>&1 | awk '{print $2}')
if [ "$PYTHON_ACTIVE_VERSION" != "$PYTHON_VERSION" ]; then
    log " ERROR - Python version is $PYTHON_ACTIVE_VERSION, expected $PYTHON_VERSION"
    exit 1
fi
log "✓ Python version confirmed: $PYTHON_ACTIVE_VERSION"

log "-- CD to mac_pytorch_inf_v2_resources"
cd "$BIN_DIR/mac_pytorch_inf_v2_resources"
check $?

# --- Validate per-scenario venv and required imports ---
# Prep stages all Python packages into a private venv under this scenario's
# resource directory. We invoke that venv's python by absolute path to
# bypass any pyenv/global-env instability caused by other scenarios. If the
# venv is missing or an expected package is not importable, fail fast with a
# clear diagnostic instead of a cryptic ImportError partway through the
# workload.
VENV_PYTHON="$BIN_DIR/mac_pytorch_inf_v2_resources/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    log " ERROR - mac_pytorch_inf_v2 venv missing at $VENV_PYTHON"
    log " ERROR - Prep state is corrupt. Re-prep required:"
    log " ERROR -   delete /Users/Shared/hobl_bin/prep_status/mac_pytorch_inf_v2<version> on the DUT and re-run."
    exit 1
fi
log "Using venv python: $VENV_PYTHON"

log "Validating venv has required packages..."
"$VENV_PYTHON" -c "import torch, transformers, mlx, mlx_lm; print('torch', torch.__version__, '| transformers', transformers.__version__, '| mlx', mlx.__version__)" >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    log " ERROR - venv has missing/broken Python packages (import failed)."
    log " ERROR - Possible causes: disk cleanup, interrupted prep, or external tampering."
    log " ERROR - Re-prep required:"
    log " ERROR -   delete /Users/Shared/hobl_bin/prep_status/mac_pytorch_inf_v2<version> on the DUT and re-run."
    exit 1
fi

# run_benchmark.py writes mac_pytorch_inf_v2_inference_info.csv to --log-dir
# with canonical HOBL keys (scenario_runtime, tokens_per_second,
# total_tokens_generated, total_generation_time_s, ai_model, ai_device,
# architecture) plus mac_pytorch_inf_v2-specific metrics (cold_load_s,
# first_inference_s, compile_time_s, prefill/decode tok/s, serialized_bytes,
# peak_memory_bytes, median/p95/CV fields, framework).
INFERENCE_CSV="$LOG_DIR/mac_pytorch_inf_v2_inference_info.csv"
log "-- Metrics will be stored in $INFERENCE_CSV"

log "-- Running mac_pytorch_inf_v2 inferencing (model_tier=$MODEL_TIER lane=$LANE quant=$QUANT shape=$SHAPE)"
if [ -n "$NO_GPU_FLAG" ]; then
    log "Running in CPU-only mode (--no-gpu)"
fi

"$VENV_PYTHON" run_benchmark.py --model-tier "$MODEL_TIER" --lane "$LANE" --quant "$QUANT" --shape "$SHAPE" --log-dir "$LOG_DIR" $NO_GPU_FLAG > "$LOG_DIR/mac_pytorch_inf_v2_output.txt" 2>&1
check $?

log "-- Parsing inference metrics"

if [ -f "$INFERENCE_CSV" ]; then
    scenario_runtime=$(grep "^scenario_runtime," "$INFERENCE_CSV" | cut -d',' -f2)
    time_to_first_token_ms=$(grep "^time_to_first_token_ms," "$INFERENCE_CSV" | cut -d',' -f2)
    time_to_first_token_s=$(grep "^time_to_first_token_s," "$INFERENCE_CSV" | cut -d',' -f2)
    tokens_per_second=$(grep "^tokens_per_second," "$INFERENCE_CSV" | cut -d',' -f2)
    total_tokens_generated=$(grep "^total_tokens_generated," "$INFERENCE_CSV" | cut -d',' -f2)
    total_generation_time_s=$(grep "^total_generation_time_s," "$INFERENCE_CSV" | cut -d',' -f2)
    ai_model=$(grep "^ai_model," "$INFERENCE_CSV" | cut -d',' -f2)
    ai_device=$(grep "^ai_device," "$INFERENCE_CSV" | cut -d',' -f2)
    framework=$(grep "^framework," "$INFERENCE_CSV" | cut -d',' -f2)
else
    log " ERROR - Inference metrics file not found: $INFERENCE_CSV"
    exit 1
fi

SCENARIO_RUNTIME=${scenario_runtime:-0}

log ""
log "========================================"
log "mac_pytorch_inf_v2 Metrics Summary"
log "========================================"
log "Model:               $ai_model"
log "Device:              $ai_device (framework: $framework)"
log "Model Tier/Lane/Quant/Shape: $MODEL_TIER / $LANE / $QUANT / $SHAPE"
log "Time to First Token: ${time_to_first_token_ms}ms (${time_to_first_token_s}s)"
log "Tokens per Second:   $tokens_per_second"
log "Total Tokens:        $total_tokens_generated"
log "Generation Time:     ${total_generation_time_s}s"
log "Architecture:        $ARCH"
log "Scenario Runtime:    ${SCENARIO_RUNTIME}s"
log "========================================"

# Copy every key/value line run_benchmark.py produced, then append HOBL's
# own architecture key -- same convention as the Windows run.ps1 script.
if [ -f "$INFERENCE_CSV" ]; then
    cp "$INFERENCE_CSV" "$METRICS_FILE"
    echo "architecture,$ARCH" >> "$METRICS_FILE"
fi
log "Metrics saved to: $METRICS_FILE"

log "-- mac_pytorch_inf_v2 run completed"

END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))

if [ ! -f "$TIME_TRACE_FILE" ]; then
    echo "Timestamp,scenario_runtime" > "$TIME_TRACE_FILE"
fi
if [ ! -f "$TOTAL_TOKEN_TRACE_FILE" ]; then
    echo "Timestamp,total_tokens" > "$TOTAL_TOKEN_TRACE_FILE"
fi
if [ ! -f "$TPS_TRACE_FILE" ]; then
    echo "Timestamp,tokens_per_second" > "$TPS_TRACE_FILE"
fi

echo "$ELAPSED_TIME,$SCENARIO_RUNTIME" >> "$TIME_TRACE_FILE"
echo "$ELAPSED_TIME,$total_tokens_generated" >> "$TOTAL_TOKEN_TRACE_FILE"
echo "$ELAPSED_TIME,$tokens_per_second" >> "$TPS_TRACE_FILE"

exit 0
