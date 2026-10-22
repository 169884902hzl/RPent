#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-postfix-exact-r3
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=02:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
LAUNCHER="$ROOT/source_attached_staged_20261022/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py"
ARGS=(--source "$ROOT/source_postfix_exact_r3_594a9de7"
    --manifest "$ROOT/results/bounded_skills/execution_repairs_20261022/postfix_object_task_exact_r3/manifest.json"
    --output "$ROOT/results/bounded_skills/execution_repairs_20261022/postfix_object_task_exact_r3/probes"
    --common-starts "$ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/common_starts"
    --initial-mode restore --indices 29)
CUDA_VISIBLE_DEVICES='' "$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
