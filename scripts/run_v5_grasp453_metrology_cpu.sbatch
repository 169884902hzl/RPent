#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=00:15:00
#SBATCH --job-name=libero-grasp453-cpu
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp451_truth_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
exec "$ROOT/.venv/bin/python" -u "$ROOT/runtime_launchers/probe_v5_grasp453_metrology_cpu.py" \
  --manifest "$ROOT/results/harness_v5/grasp451_sustained_truth_20261005/preparation/smoke.json" \
  --output "$ROOT/results/harness_v5/grasp453_metrology_CPU_20261005/job${SLURM_JOB_ID}"
