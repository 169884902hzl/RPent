#!/usr/bin/env bash
# One visited original microwave development smoke; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --job-name=microwave-temporal-smoke
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
MICROWAVE_ROOT=/public/home/sunyihan/rpent_libero_eval
MICROWAVE_SOURCE=${MICROWAVE_SOURCE:?new immutable source required}
MICROWAVE_PLAN=${MICROWAVE_PLAN:?absolute explicit original one-case plan required}
MICROWAVE_PLAN_SHA=${MICROWAVE_PLAN_SHA:?manifest SHA required}
MICROWAVE_OUTPUT=${MICROWAVE_OUTPUT:?fresh absolute output required}
export PYTHONPATH="$MICROWAVE_SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$MICROWAVE_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$MICROWAVE_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$MICROWAVE_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
"$MICROWAVE_ROOT/.venv/bin/python" - "$MICROWAVE_SOURCE" "$MICROWAVE_PLAN" "$MICROWAVE_PLAN_SHA" "$MICROWAVE_OUTPUT" <<'PY'
import hashlib,json,sys
from pathlib import Path
source,plan_path,output=map(Path,(sys.argv[1],sys.argv[2],sys.argv[4]))
if not all(path.is_absolute() for path in (source,plan_path,output)):
    raise ValueError('absolute source/manifest/output required')
if hashlib.sha256(plan_path.read_bytes()).hexdigest()!=sys.argv[3]:
    raise ValueError('manifest SHA changed')
plan=json.loads(plan_path.read_text())
if (plan['cohort']!='development' or len(plan['cases'])!=1 or plan['new_training_rows']!=0
        or plan['cases'][0]['episode']['suite'] not in ('libero_spatial','libero_object','libero_goal','libero_10','libero_90')):
    raise ValueError('one explicit original visited development case required')
identity=plan['source_snapshot']
if Path(identity['path'])!=source:
    raise ValueError('source snapshot identity differs from launcher source')
for ref in [*identity['files'],identity['archive'],plan['producer'],*plan['producer_dependencies'],plan['adapter'],plan['launcher']]:
    path=Path(ref['path'])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError('pinned source/dependency changed: '+str(path))
required=('robots/libero/v5_microwave_capture.py','robots/libero/v5_microwave_door_temporal.py',
          'robots/libero/v5_runtime.py','scripts/probe_v5_microwave_public571.py',
          'scripts/probe_v5_skill501_original.py','scripts/v5_probe_preflight.py',
          'typed_choice_eval.py')
for name in required:
    if not (source/name).is_file():raise FileNotFoundError(source/name)
if not Path(plan['base_config']['path']).is_absolute():
    raise ValueError('base_config must be absolute before submission')
from scripts.v5_probe_preflight import load_pinned_manifest
from scripts.probe_v5_skill501_original import validate_manifest
load_pinned_manifest(plan_path,validate_manifest)
if output.exists():raise FileExistsError(output)
PY
cd /tmp
if [[ "${MICROWAVE_CPU_ONLY:-0}" == 1 ]]; then
  exec "$MICROWAVE_ROOT/.venv/bin/python" "$MICROWAVE_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MICROWAVE_PLAN" --shard-index 0 --shards 1 --states
fi
set +e
"$MICROWAVE_ROOT/.venv/bin/python" -u "$MICROWAVE_SOURCE/scripts/probe_v5_microwave_public571.py" \
  --manifest "$MICROWAVE_PLAN" --output "$MICROWAVE_OUTPUT" --shard-index 0 --shards 1
MICROWAVE_RC=$?
set -e
"$MICROWAVE_ROOT/.venv/bin/python" - "$MICROWAVE_OUTPUT" "$MICROWAVE_RC" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); rc=int(sys.argv[2]); path=root/'episodes.jsonl'
if not path.is_file():raise SystemExit('startup_error: no episode ledger')
rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
if len(rows)!=1:raise SystemExit('startup_error: expected one development episode')
row=rows[0]
if rc:raise SystemExit(rc)
if row.get('raised_error') or row.get('infrastructure_failure') or row.get('status') in ('startup','startup_error','infrastructure_error'):
    raise SystemExit('startup/development_error: inspect preserved attempt')
first=row.get('first_attempt') or {}
controls=(row.get('server_chunk_execution') or {}).get('requested_controls',0)
if int(controls)<=0 or first.get('physically_executed') is not True:
    raise SystemExit('startup_error: no requested physical controls for the selected skill')
records=(first.get('verification_measurements') or {}).get('microwave_temporal',[])
(root/'physical_startup_contract.json').write_text(json.dumps({
    'status':'pass','case':row['case']['name'],'requested_controls':controls,
    'temporal_records':len(records),'physics_result_is_skill_qualification':False,
},indent=2)+'\n')
PY
