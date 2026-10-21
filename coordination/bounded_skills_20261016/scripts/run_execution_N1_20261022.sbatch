#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-execution-N1
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
: "${EXEC_SOURCE:?absolute archived source}"
: "${EXEC_MANIFEST:?absolute registered plan}"
: "${EXEC_OUTPUT:?new result directory}"
: "${EXEC_COMMON:?original complete physical initial states}"
: "${EXEC_INDICES:?registered N1 indices}"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
read -r -a INDEX_ARGS <<< "$EXEC_INDICES"
LAUNCHER="$EXEC_SOURCE/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py"
ARGS=(--source "$EXEC_SOURCE" --manifest "$EXEC_MANIFEST" --output "$EXEC_OUTPUT" --common-starts "$EXEC_COMMON" --initial-mode restore --indices "${INDEX_ARGS[@]}")
CUDA_VISIBLE_DEVICES='' "$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
# Same snapshot and launcher performs a real one-chunk startup before cases.
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
