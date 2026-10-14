#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:40:00
#SBATCH --job-name=grasp-confirm-reset-probe
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-reset-probe-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
PLAN="$ROOT/results/harness_v5/geometric_grasp_confirmation_20261010_r1/bowl/preparation/confirmation.json"
eval "$("$ROOT/.venv/bin/python" - "$PLAN" <<'PY'
import json,shlex,sys
plan=json.load(open(sys.argv[1]))
for name,key in [('RESET_PROBE_SOURCE','source_path'),('RESET_PROBE_ADAPTER','adapter_path')]:
    print(name+'='+shlex.quote(plan[key]))
PY
)"
export PYTHONPATH="$RESET_PROBE_ADAPTER:$RESET_PROBE_SOURCE:$ROOT" LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export LIBERO_GRASP_DIAGNOSTIC_MODELS="$ROOT/coordination/private_grasp_models_v3r9"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd /tmp
"$ROOT/.venv/bin/python" -u -m coordination.probe_confirmation_env_reset_20261010 \
 --plan "$PLAN" --faults "$ROOT/coordination/confirmation_env_reset_faults_20261010_r1.json" \
 --output "$ROOT/coordination/confirmation_env_reset_probe_20261010_r1"
