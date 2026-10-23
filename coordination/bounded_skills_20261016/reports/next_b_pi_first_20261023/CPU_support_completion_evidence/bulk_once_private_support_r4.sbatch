#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-train-dagger-priority1
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=08:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PI05_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/pi05 SAM3_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config_original_20261023
TASK=$(printf '%03d' "$SLURM_ARRAY_TASK_ID")
MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1/preparation/bulk_shard$TASK.json
OUTPUT=/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1/shard$TASK
export LIBERO_GRASP_DIAGNOSTIC_MODELS="$OUTPUT/private_grasp_models"
EXPORT=/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1/exports/shard${TASK}_job${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/entry_snapshots/df827a58936949c2a4044fa6f45fe16523442bb8709dc1061cd876720a2abfb8.py --manifest "$MANIFEST" --output "$OUTPUT"
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/entry_snapshots/d9c06ef604b1cd95aaf41e5079924cba2c39f0ba5739b9af4f33667603994541.py --source /public/home/sunyihan/rpent_libero_eval/source_pi_first_origin_f6ce1d46_20261023 --manifest "$MANIFEST" --results "$OUTPUT" --policy-hashes /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/qualified90_9716b68c/preparation/registered_pi05_hashes.sha256 --measurement-helper /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/entry_snapshots/612082b8d56b23472f704db8b73b6377287105e6566831df2747873e98251cb8.py --prompt-helper /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/entry_snapshots/6142d6cdaf2002362724298b329d3619f04ebf7d3499b9d0e5363cceafd499ef.py --output "$EXPORT"
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/entry_snapshots/51211e37cba77199255e63052d8208459db4b2576385ea80372a22fd944cb005.py --package "$EXPORT" --name C3_DAGGER_ONCE_shard${TASK}_job${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}
