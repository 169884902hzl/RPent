#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-refresh-N130
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=04:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --array=0-2%3
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export EXEC_SOURCE="$ROOT/source_refresh_ablation_20261022"
export EXEC_MANIFEST="$ROOT/results/bounded_skills/execution_repairs_20261022/refresh_ablation/manifest.json"
export EXEC_OUTPUT="$ROOT/results/bounded_skills/execution_repairs_20261022/refresh_ablation/N1_30/shard${SLURM_ARRAY_TASK_ID}"
export EXEC_COMMON="$ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/common_starts"
"$ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
p=Path('/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/refresh_ablation/probes/case023/summary.json')
x=json.loads(p.read_bytes())
assert x['success'] and x['sim_steps']>0
assert x['source_commit']=='9d00ee63ab2196b95f8374e8245d9dea2ed8782b'
PY
case "$SLURM_ARRAY_TASK_ID" in
    0) export EXEC_INDICES='0 1 2 3 4 5 6 7 8 9' ;;
    1) export EXEC_INDICES='10 11 12 13 14 15 16 17 18 19' ;;
    2) export EXEC_INDICES='20 21 22 23 26 27 28 29 30 31' ;;
    *) exit 2 ;;
esac
exec bash "$EXEC_SOURCE/coordination/bounded_skills_20261016/scripts/run_execution_N1_20261022.sbatch"
