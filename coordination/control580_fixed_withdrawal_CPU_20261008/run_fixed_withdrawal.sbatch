#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-8%1
#SBATCH --job-name=libero-fixed-withdrawal
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_CPU_20261008/preparation_r1
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
export PI05_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/pi05
export SAM3_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
FIXED_WITHDRAWAL_RUN=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_original_20261008/probe_job${SLURM_ARRAY_JOB_ID}
mkdir -p "$FIXED_WITHDRAWAL_RUN"
cd /tmp
FIXED_WITHDRAWAL_ARGS=(--manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_CPU_20261008/preparation_r1/capture_manifest.json --manifest-sha256 1eb0e88a3721d9b4ea93ac2c66b6d3488436e8e98c59052f71dbea126d57c6d5 --shard-index "$SLURM_ARRAY_TASK_ID")
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_CPU_20261008/preparation_r1/capture_fixed_withdrawal.py "${FIXED_WITHDRAWAL_ARGS[@]}" --preflight-only --preflight-report "$FIXED_WITHDRAWAL_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
if [[ "${FIXED_WITHDRAWAL_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u /public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_CPU_20261008/preparation_r1/capture_fixed_withdrawal.py "${FIXED_WITHDRAWAL_ARGS[@]}" --output "$FIXED_WITHDRAWAL_RUN/part${SLURM_ARRAY_TASK_ID}"
