#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-original-exclusion-cpu
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=2
#SBATCH --mem=40G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export CUDA_VISIBLE_DEVICES=''
exec "$ROOT/.venv/bin/python" "$ROOT/coordination/bounded_skills_20261016/scripts/reconstruct_original_confirmation_geometry_CPU_20261022.py" \
    --source "$ROOT/source_postN1_aa433ad9_20261022" \
    --registry "$ROOT/coordination/owner_alerts/Codex3/CONFIRMATION_REGISTRY_RECONCILIATION.json" \
    --registry-sha256 fa5001d9941dcac96cd5db95edf7426ed827c5c717677957a39651e677f4225a \
    --output "$ROOT/results/bounded_skills/execution_repairs_20261022/perturbation_guard_CPU/original665_geometry"
