#!/bin/bash
#SBATCH --job-name=rpent-choice
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
cd "$ROOT"
export PYTHONPATH="$ROOT"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"

MODEL_PY=/public/home/sunyihan/robot_decider/runtime/.venv/bin/python
RPENT_PY="$ROOT/.venv/bin/python"
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
BASE=/public/home/sunyihan/rd_instruction_20260923/v5_models/qwen3_5_4b_851bf6e8
CHECKPOINT=/public/home/sunyihan/rd_instruction_20260923/dagger_counterfactual_sft_v2_20260928/checkpoint_dagger_counterfactual

MODELS="${MODELS:-dagger2323 qwen4b}"
SUITES="${SUITES:-libero_spatial_swap libero_object_swap}"
TASKS="${TASKS:-0 1 2 3 4 5 6 7 8 9}"
RESULTS_ROOT="${RESULTS_ROOT:-results}"
MAX_DECISIONS="${MAX_DECISIONS:-15}"
mkdir -p "$RESULTS_ROOT"

for model in $MODELS; do
    if [ "$model" = jev ]; then
        choice_endpoint=http://127.0.0.1:18574
        curl -fsS "$choice_endpoint/health" > /dev/null
    else
        choice_endpoint=http://127.0.0.1:18573
        "$MODEL_PY" qwen_choice_service.py --model "$model" --package "$PACKAGE" \
            --base "$BASE" --checkpoint "$CHECKPOINT" --port 18573 \
            > "results/choice-service-${SLURM_JOB_ID}-${model}.log" 2>&1 &
        service_pid=$!
        trap 'kill "$service_pid" 2>/dev/null || true' EXIT
        ready=0
        for attempt in $(seq 1 120); do
            if curl -fsS "$choice_endpoint/health" > /dev/null 2>&1; then
                ready=1
                break
            fi
            if ! kill -0 "$service_pid" 2>/dev/null; then
                break
            fi
            sleep 2
        done
        if [ "$ready" -ne 1 ]; then
            echo "Choice service failed to start: $model"
            exit 1
        fi
    fi
    for suite in $SUITES; do
        for task in $TASKS; do
            out="$RESULTS_ROOT/${model}/${suite}/task_${task}_seed_0"
            "$RPENT_PY" typed_choice_eval.py --suite "$suite" --task "$task" \
                --seed 0 --provider "$model" \
                --max-decisions "$MAX_DECISIONS" \
                --choice-endpoint "$choice_endpoint" \
                --output-dir "$out"
        done
    done
    if [ "$model" != jev ]; then
        kill "$service_pid"
        wait "$service_pid" 2>/dev/null || true
        trap - EXIT
    fi
done
