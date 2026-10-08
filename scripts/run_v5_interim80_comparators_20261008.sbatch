#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=130G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --job-name=libero-interim80
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${INTERIM80_SOURCE:?absolute immutable source required}
PREP=${INTERIM80_PREP:?absolute preparation required}
COHORT=${INTERIM80_COHORT:?A4-N or RULE-N required}
PART=${SLURM_ARRAY_TASK_ID:-0}
STARTUP=${INTERIM80_STARTUP_PREFLIGHT:-0}
CONTRACT=${INTERIM80_STARTUP_CONTRACT:-}
PLAN="$PREP/${COHORT}_part${PART}.json"
LAUNCHER="$0"
OUTROOT=${INTERIM80_OUTPUT_ROOT:-$ROOT/results/harness_v5/interim574_20261007}
OUT="$PREP/launcher_preflight/${COHORT}_part${PART}"
if [[ "${INTERIM80_PREFLIGHT_ONLY:-0}" != 1 ]]; then
 if [[ "$STARTUP" == 1 ]]; then
  OUT="$OUTROOT/$COHORT/startup_preflight/job${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-manual}}/part${PART}"
 else
  OUT="$OUTROOT/$COHORT/job${SLURM_ARRAY_JOB_ID:?array job ID required}/part${PART}"
 fi
fi
mkdir -p "$OUT"
export PYTHONPATH="$SOURCE" LIBERO_CONFIG_PATH="$ROOT/runtime_config" PYTHONDONTWRITEBYTECODE=1
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602" LIBERO_TYPE=pro
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$PLAN" "$PREP" "$SOURCE" "$LAUNCHER" <<'PINS'
import hashlib,json,sys
from pathlib import Path
plan,prep,source,launcher=map(Path,sys.argv[1:])
assert all(p.is_absolute() for p in (plan,prep,source,launcher))
index=json.loads((prep/'manifest.json').read_text());payload=json.loads(plan.read_text())
assert payload['source_path']==index['source_path']==str(source)
assert payload['source_commit']==index['source_commit']
assert payload['cohort'] in ('A4-N','RULE-N') and payload['libero_type']=='pro'
assert payload['training_allowed'] is False and payload['behavior_frozen'] is False
assert payload['budget']['success_prediction_diagnostic'] is False
assert len(payload['episodes'])==10
for item in [*index['files'],*index['references'],*index['source_snapshot']['files'],
             index['source_snapshot']['archive'],index['batch_runner'],index['launcher'],
             index['jev_systemone_bridge'],*index.get('runtime_supplement',[])]:
 path=Path(item['path']);assert path.is_absolute() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],str(path)
assert hashlib.sha256(launcher.read_bytes()).hexdigest()==index['launcher']['sha256']
assert Path(index['batch_runner']['path']).resolve()==(source/'v5_batch_eval.py').resolve()
for resource in [source/'harness_v5_eval.py',source/'robots/libero/v5_state.py',source/'typed_choice_eval.py',
                 source/'scripts/preflight_v5_runtime536_smoke.py',
                 Path('/public/home/sunyihan/rpent_libero_eval/.venv/bin/python'),
                 Path('/public/home/sunyihan/rpent_libero_eval/runtime_config/config.yaml'),
                 Path('/public/home/sunyihan/rpent_libero_eval/assets/pi05'),
                 Path('/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt')]:
 assert resource.exists(),str(resource)
PINS
"$ROOT/.venv/bin/python" - "$SOURCE" <<'IMPORTS'
import sys
from pathlib import Path
from transformers import AutoTokenizer
from robots.libero.robot_spec import _init_runtime
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_env_client import V5SkillEnvClient
from robots.libero.v5_runtime import MeasuredScene,V5Executor
from rpent.dashboard.events import NullDashboardEventSink
from rpent.memory import MemoryManager
from typed_choice_eval import ChoiceScorer
from robots.libero.v5_systemone import score
import typed_choice_eval
assert Path(typed_choice_eval.__file__).resolve()==Path(sys.argv[1])/'typed_choice_eval.py'
IMPORTS
cd /tmp
"$ROOT/.venv/bin/python" "$SOURCE/scripts/preflight_v5_runtime536_smoke.py" --assets "$PLAN" --output "$OUT/assets.json"
"$ROOT/.venv/bin/python" - "$PLAN" "$OUT" <<'HEALTH'
import json,sys
from pathlib import Path
from urllib.request import urlopen
plan,out=map(Path,sys.argv[1:]);payload=json.loads(plan.read_text())
with urlopen(payload['choice_endpoint'].rstrip('/')+'/health',timeout=15) as response:health=json.load(response)
assert health['model']==payload['expected_model'],health
if payload['cohort']=='A4-N':assert health['identity_verified'] is True,health
else:assert health['revision']==payload['model_revision'],health
(out/'upstream_identity.json').write_text(json.dumps(health,indent=2)+'\n')
HEALTH
if [[ "${INTERIM80_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
"$ROOT/.venv/bin/python" - "$PLAN" "$PREP" "$SOURCE" "$LAUNCHER" "$OUT" "$STARTUP" "$CONTRACT" <<'PLAN'
import hashlib,json,sys
from pathlib import Path
plan,prep,source,launcher,out=map(Path,sys.argv[1:6]);startup,contract=sys.argv[6:]
payload=json.loads(plan.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
identity={'cohort':payload['cohort'],'source_path':str(source),'source_commit':payload['source_commit'],
          'manifest_index_sha256':sha(prep/'manifest.json'),'launcher_sha256':sha(launcher),
          'expected_model':payload['expected_model'],'upstream_endpoint':payload['choice_endpoint']}
if startup=='1':payload['episodes']=payload['episodes'][:1]
else:
 if not contract:raise SystemExit('formal array requires the same-source, same-launcher physical startup contract')
 startup_record=json.loads(Path(contract).resolve(strict=True).read_text())
 if startup_record.get('status')!='pass' or any(startup_record.get(k)!=v for k,v in identity.items()):
  raise SystemExit('startup contract differs from this comparator source/launcher/endpoint')
 if not startup_record.get('physical_actions'):raise SystemExit('startup has no executed physical action')
 payload['episodes']=[episode for episode in payload['episodes'] if episode!=startup_record['episode']]
payload['launcher_execution_identity']=identity
payload['parent_plan']={'path':str(plan),'sha256':sha(plan)}
path=out/'runtime_plan.json'
if path.exists():raise SystemExit('preserve the previous runtime plan; use a new job')
path.write_text(json.dumps(payload,indent=2)+'\n')
PLAN
PLAN="$OUT/runtime_plan.json"
ENDPOINT=$("$ROOT/.venv/bin/python" - "$PLAN" <<'ENDPOINT'
import json,sys
print(json.load(open(sys.argv[1]))['choice_endpoint'])
ENDPOINT
)
if [[ "$COHORT" == A4-N ]]; then
 BRIDGE=$("$ROOT/.venv/bin/python" - "$PREP/manifest.json" <<'BRIDGE'
import json,sys
print(json.load(open(sys.argv[1]))['jev_systemone_bridge']['path'])
BRIDGE
)
 PORT=$("$ROOT/.venv/bin/python" -c 'from rpent.utils.daemon import pick_free_port; print(pick_free_port())')
 "$ROOT/.venv/bin/python" -u "$BRIDGE" --upstream "$ENDPOINT" --port "$PORT" > "$OUT/jev_bridge.log" 2>&1 &
 bridge_pid=$!
 trap 'kill "$bridge_pid" 2>/dev/null || true; wait "$bridge_pid" 2>/dev/null || true' EXIT
 ENDPOINT="http://127.0.0.1:$PORT"
 "$ROOT/.venv/bin/python" - "$ENDPOINT" "$bridge_pid" "$OUT" <<'BRIDGE_HEALTH'
import json,os,sys,time
from pathlib import Path
from urllib.request import urlopen
endpoint,pid,out=sys.argv[1],int(sys.argv[2]),Path(sys.argv[3]);deadline=time.monotonic()+30
while True:
 try:
  with urlopen(endpoint+'/health',timeout=5) as response:health=json.load(response)
 except OSError:
  os.kill(pid,0)
  if time.monotonic()>deadline:raise RuntimeError('official relay bridge did not start')
  time.sleep(0.2);continue
 assert health['model']=='jev-1.13.0' and health['identity_verified'] is True
 (out/'model_identity.json').write_text(json.dumps(health,indent=2)+'\n');break
BRIDGE_HEALTH
else
 cp "$OUT/upstream_identity.json" "$OUT/model_identity.json"
fi
cd "$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
set +e
"$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" --provider systemone --choice-endpoint "$ENDPOINT" --manifest "$PLAN" --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/probe"
RUN_RC=$?
set -e
"$ROOT/.venv/bin/python" - "$PLAN" "$OUT" "$RUN_RC" "$STARTUP" <<'EXIT'
import hashlib,json,sys
from pathlib import Path
plan,out=map(Path,sys.argv[1:3]);rc=int(sys.argv[3]);startup=sys.argv[4]=='1'
ledger=out/'probe/episodes.jsonl'
if not ledger.exists():raise SystemExit('runner produced no terminal ledger')
rows=[json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
if not rows:raise SystemExit('runner produced no attempted episode')
infra=[row['episode'] for row in rows if not row['result'].get('official_success') and
       (row['result'].get('infrastructure_failure') or row['result'].get('status') in ('startup','startup_error')
        or row['result'].get('termination_category')=='startup_error')]
if infra:
 print(json.dumps({'startup_or_infrastructure_errors':infra}),file=sys.stderr);raise SystemExit(2)
if rc:raise SystemExit(rc)
if startup:
 if len(rows)!=1:raise SystemExit('startup must preserve exactly one episode')
 row=rows[0];choices=Path(row['output_dir'])/'choices.jsonl'
 if not choices.exists():raise SystemExit('startup contains no actual decision trace')
 events=[json.loads(line) for line in choices.read_text().splitlines() if line.strip()]
 physical=[];payload=json.loads(plan.read_text())
 for event in events:
  if event.get('answer',{}).get('model')!=payload['expected_model']:raise SystemExit('decision model identity changed')
  receipt=event.get('receipt') or {}
  chunks=max(int(receipt.get('chunks',0) or 0),int((receipt.get('primitive_result') or {}).get('chunks_used',0) or 0))
  steps=sum(int(e.get('steps_used',0) or 0) for e in event.get('motion_evidence',[]))
  if chunks or steps:physical.append({'decision':event['decision'],'selected':event['selected'],'executed_chunks':chunks,'executed_motion_steps':steps})
 if not physical:raise SystemExit('startup produced no actual physical execution')
 contract={**payload['launcher_execution_identity'],'status':'pass','episode':row['episode'],
           'physical_actions':physical,'parent_plan':payload['parent_plan'],
           'startup_only_not_skill_qualification':True,
           'episodes':{'path':str(ledger),'sha256':hashlib.sha256(ledger.read_bytes()).hexdigest()},
           'choices':{'path':str(choices),'sha256':hashlib.sha256(choices.read_bytes()).hexdigest()}}
 (out/'startup_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
EXIT
