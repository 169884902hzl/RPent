#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-a4-table97-tail4
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=12:00:00
#SBATCH --nice=1
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_table97_20261001"
OUT="$ROOT/results/harness_v5/a4_jev_table97_tail4_20261001/job${SLURM_JOB_ID}"
mkdir -p "$OUT"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
sha256sum "$SOURCE/harness_v5_eval.py" "$SOURCE/v5_batch_eval.py" \
 "$SOURCE/robots/libero/v5_runtime.py" "$SOURCE/robots/libero/v5_state.py" \
 "$ROOT/results/harness_v5/a4_jev_table97_tail4_20261001/preparation/remaining4.json" \
 "$ROOT/runtime_launchers/run_v5_a4_table97_tail4_20261001.sbatch" > "$OUT/source.sha256"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$ROOT/results/harness_v5/a4_jev_table97_tail4_20261001/preparation/remaining4.json" \
 --provider jev \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --choice-endpoint "${JEV_ENDPOINT:-http://10.10.223.2:18582}" \
 --pause-marker "$ROOT/results/harness_v5/a4_jev_table97_tail4_20261001/PAUSE_REQUESTED_job${SLURM_JOB_ID}" \
 --output-dir "$OUT/episodes"
