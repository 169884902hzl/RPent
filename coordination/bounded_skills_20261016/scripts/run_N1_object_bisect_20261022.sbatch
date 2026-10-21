#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-object-bisect
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=06:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --array=0-1%2
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
case "$SLURM_ARRAY_TASK_ID" in
    0) COMMIT="${BISECT_PARENT:-99d90ae8}" ;;
    1) COMMIT="${BISECT_CHILD:-daaa1730}" ;;
    *) exit 2 ;;
esac
export EXEC_SOURCE="$ROOT/source_bisect_${COMMIT}_D3_20261022"
export EXEC_MANIFEST="$ROOT/results/bounded_skills/execution_repairs_20261022/object_bisect_${COMMIT}/manifest.json"
export EXEC_OUTPUT="$ROOT/results/bounded_skills/execution_repairs_20261022/object_bisect_${COMMIT}/probes"
export EXEC_COMMON="$ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/common_starts"
export EXEC_INDICES="${BISECT_INDICES:-26 27 29}"
# Historical snapshots used startup aliases only available at old shard heads.
# Use the registered canonical-state launcher for both bisect arms.
LAUNCHER="$ROOT/source_attached_staged_20261022/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
read -r -a INDICES <<< "$EXEC_INDICES"
ARGS=(--source "$EXEC_SOURCE" --manifest "$EXEC_MANIFEST" --output "$EXEC_OUTPUT"
    --common-starts "$EXEC_COMMON" --initial-mode restore --indices "${INDICES[@]}")
CUDA_VISIBLE_DEVICES='' "$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
