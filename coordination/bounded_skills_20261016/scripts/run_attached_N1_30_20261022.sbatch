#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-attached-N1-30
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --array=0-2%2
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export SOURCE_COMMIT=0514333776503c8af58d2ab656b8a3393c168a22
export EXEC_SOURCE="$ROOT/source_attached_staged_20261022"
export EXEC_MANIFEST="$ROOT/results/bounded_skills/execution_repairs_20261022/05143337/preparation/N1_fixed32_r2.json"
export EXEC_COMMON="$ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/common_starts"
export EXEC_OUTPUT="$ROOT/results/bounded_skills/execution_repairs_20261022/05143337/N1_30/shard${SLURM_ARRAY_TASK_ID}"
case "$SLURM_ARRAY_TASK_ID" in
    0) export EXEC_INDICES='0 1 2 3 4 5 6 7 8 9' ;;
    1) export EXEC_INDICES='10 11 12 13 14 15 16 17 18 19' ;;
    2) export EXEC_INDICES='20 21 22 23 26 27 28 29 30 31' ;;
    *) exit 2 ;;
esac
exec bash "$EXEC_SOURCE/coordination/bounded_skills_20261016/scripts/run_execution_N1_20261022.sbatch"
