#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-latency-fixed32
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
: "${LATENCY_LAUNCHER:?absolute pinned launcher required}"
: "${BASELINE_MANIFEST:?absolute pinned baseline manifest required}"
: "${OPTIMIZED_MANIFEST:?absolute pinned optimized manifest required}"
: "${LATENCY_OUTPUT:?fresh output directory required}"
test ! -e "$LATENCY_OUTPUT"
mkdir -p "$LATENCY_OUTPUT"
for arm in baseline optimized; do
    if [[ "$arm" == baseline ]]; then manifest=$BASELINE_MANIFEST; else manifest=$OPTIMIZED_MANIFEST; fi
    source_dir=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["baseline_source"])' "$manifest")
    "$ROOT/.venv/bin/python" "$LATENCY_LAUNCHER" --manifest "$manifest" --source "$source_dir" \
        --output "$LATENCY_OUTPUT/preflight_$arm" --preflight
    "$ROOT/.venv/bin/python" -u "$LATENCY_LAUNCHER" --manifest "$manifest" --source "$source_dir" \
        --output "$LATENCY_OUTPUT/startup_$arm" --startup-only
done
# Both exact sources/launcher have now completed a real physical request.
for arm in baseline optimized; do
    if [[ "$arm" == baseline ]]; then manifest=$BASELINE_MANIFEST; else manifest=$OPTIMIZED_MANIFEST; fi
    source_dir=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["baseline_source"])' "$manifest")
    "$ROOT/.venv/bin/python" -u "$LATENCY_LAUNCHER" --manifest "$manifest" --source "$source_dir" \
        --output "$LATENCY_OUTPUT/$arm"
done
