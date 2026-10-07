#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-2%3
#SBATCH --nice=1000
#SBATCH --job-name=libero-control-capture
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006:/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
export PI05_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/pi05
export SAM3_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CONTROL_CAPTURE_RUN=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_off320_original_r4_20261008/probe_job${SLURM_ARRAY_JOB_ID}
mkdir -p "$CONTROL_CAPTURE_RUN"
cd /tmp
CONTROL_CAPTURE_ARGS=(--manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/capture_manifest.json --manifest-sha256 10d3dfb57daae71fb5b9b36bc27d372ef61709862d9b84187b269afbecf000a4 --shard-index "$SLURM_ARRAY_TASK_ID")
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/capture_control_sequence.py "${CONTROL_CAPTURE_ARGS[@]}" --preflight-only --preflight-report "$CONTROL_CAPTURE_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
if [[ "${CONTROL_CAPTURE_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/capture_control_sequence.py "${CONTROL_CAPTURE_ARGS[@]}" --output "$CONTROL_CAPTURE_RUN/part${SLURM_ARRAY_TASK_ID}"
