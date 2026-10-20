#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-schema6
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
: "${SCHEMA6_SOURCE:?absolute snapshot required}"
: "${SCHEMA6_MANIFEST:?absolute manifest required}"
: "${SCHEMA6_OUTPUT:?case-resumable output required}"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
if [[ "${SCHEMA6_N1:-0}" == 1 ]]; then
    LAUNCHER=${SCHEMA6_LAUNCHER:-$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py}
else
    LAUNCHER=${SCHEMA6_LAUNCHER:-$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py}
fi
ARGS=(--source "$SCHEMA6_SOURCE" --manifest "$SCHEMA6_MANIFEST" --output "$SCHEMA6_OUTPUT")
CUDA_VISIBLE_DEVICES='' "$ROOT/.venv/bin/python" - "$SCHEMA6_SOURCE" "$SCHEMA6_MANIFEST" <<'PY'
from pathlib import Path
import hashlib,json,sys
source=Path(sys.argv[1]).resolve(strict=True)
for name in ('harness_v5_eval.py','typed_choice_eval.py','scripts/probe_bounded_hybrid_d2.py'):
    if not (source/name).is_file():raise FileNotFoundError(source/name)
sys.path.insert(0,str(source))
from scripts.probe_bounded_hybrid_d2 import load_public_gripper_calibration
import harness_v5_eval
if Path(harness_v5_eval.__file__).resolve().parent!=source:
    raise RuntimeError('calibration helper imported from a different snapshot')
plan=json.loads(Path(sys.argv[2]).resolve(strict=True).read_bytes())
rows=plan.get('jobs',plan.get('cases',[]))
for row in rows:load_public_gripper_calibration(row['case']['grasp_measurement_calibration'])
print(json.dumps({'CPU_source_import_preflight':'passed','cases':len(rows),'source':str(source),
    'root_helper_sha256':hashlib.sha256((source/'harness_v5_eval.py').read_bytes()).hexdigest()}),flush=True)
PY
if [[ "${SCHEMA6_N1:-0}" != 1 ]]; then
    ARGS+=(--episode-concurrency "${SCHEMA6_CONCURRENCY:-8}")
fi
"$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
if [[ "${SCHEMA6_N1:-0}" == 1 && "${SCHEMA6_STARTUP_ONLY:-0}" != 1 ]]; then
    # The fixed cohort includes legacy saved VLA requests as well as fresh
    # episodes. Exercise that distinct restore path before the formal N1 run.
    "$ROOT/.venv/bin/python" "$LAUNCHER" --source "$SCHEMA6_SOURCE" \
        --manifest "$SCHEMA6_MANIFEST" --output "$SCHEMA6_OUTPUT/pilot_startup_check" \
        --indices 24 --startup-only
fi
if [[ "${SCHEMA6_STARTUP_ONLY:-0}" == 1 ]]; then ARGS+=(--startup-only); fi
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
