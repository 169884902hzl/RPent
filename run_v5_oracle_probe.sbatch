#!/bin/bash
#SBATCH --job-name=libero-v5-oracle-probe
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:?independent source snapshot required}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_oracle_probe.py" \
    --output "$ROOT/results/harness_v5/oracle_probe_20260929/job${SLURM_JOB_ID}.json"
