#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=12:00:00
#SBATCH --job-name=libero-perturb-skill
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
PLAN=${PERTURB_SKILL_PLAN:?absolute registered plan required}
PLAN_SHA=${PERTURB_SKILL_PLAN_SHA:?registered plan SHA required}
SOURCE=${PERTURB_SKILL_SOURCE:?immutable source required}
ADAPTER=${PERTURB_SKILL_ADAPTER:?immutable adapter required}
OUTPUT=${PERTURB_SKILL_OUTPUT:?absolute output root required}
PART=${SLURM_ARRAY_TASK_ID:-0}
STARTUP=${PERTURB_SKILL_STARTUP:-0}
export PYTHONPATH="$ADAPTER:$SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PERTURB_SKILL_LAUNCHER="$0"
export PERTURB_SKILL_OUTPUT_JOB="$OUTPUT/job${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-manual}}/part$PART"
"$ROOT/.venv/bin/python" - "$PLAN" "$PLAN_SHA" "$SOURCE" "$ADAPTER" <<'PREFLIGHT'
import hashlib,json,os,sys
from pathlib import Path
from scripts.v5_probe_preflight import load_pinned_manifest,pinned_file
from scripts.probe_v5_skill501_original import validate_manifest
import scripts.probe_v5_perturb_skill_20261009 as adapter
plan,expected,source,adapter_path=sys.argv[1:]
path=Path(plan)
if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
    raise ValueError('registered perturbation plan changed')
_,payload,_=load_pinned_manifest(path,validate_manifest)
if payload['cohort']!='selection' or payload['confirmation'] or payload['training_allowed']:
    raise ValueError('only original perturbation selection is authorized')
if payload['source_path']!=source or payload['adapter_path']!=adapter_path:
    raise ValueError('source/adapter differs from registered plan')
if Path(adapter.__file__).resolve()!=Path(adapter_path)/'scripts/probe_v5_perturb_skill_20261009.py':
    raise ValueError('perturbation adapter imported from a different path')
for r in [*payload['producer_dependencies'],*payload['references'],payload['source_snapshot']['archive']]:
    pinned_file(r,'registered_dependency')
for case in payload['cases']:
    pinned_file(case['registered_layout_state'],'registered_layout_state')
if os.environ.get('PERTURB_SKILL_CPU_ONLY')=='1':
    print(json.dumps({'CPU_preflight':'pass','registered_cases':len(payload['cases'])}));raise SystemExit()
out=Path(os.environ['PERTURB_SKILL_OUTPUT_JOB']);out.mkdir(parents=True,exist_ok=False)
identity={'plan_sha256':expected,'source_commit':payload['source_commit'],
          'launcher_sha256':hashlib.sha256(Path(os.environ['PERTURB_SKILL_LAUNCHER']).read_bytes()).hexdigest()}
if os.environ.get('PERTURB_SKILL_STARTUP')=='1':
    payload['cases']=payload['cases'][:1]
else:
    contract=json.loads(Path(os.environ['PERTURB_SKILL_STARTUP_CONTRACT']).read_text())
    if (contract['status']!='pass' or contract['physical_controls']<=0
            or any(contract[k]!=v for k,v in identity.items())):
        raise ValueError('startup contract differs from current source/launcher/plan')
    payload['cases']=[c for c in payload['cases'] if c['name']!=contract['case_name']]
payload['launcher_identity']=identity
(out/'run_manifest.json').write_text(json.dumps(payload,indent=2)+'\n')
PREFLIGHT
if [[ "${PERTURB_SKILL_CPU_ONLY:-0}" == 1 ]]; then exit 0; fi
SHARDS=${PERTURB_SKILL_SHARDS:-8}
if [[ "$STARTUP" == 1 ]]; then SHARDS=1; fi
cd /tmp
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_perturb_skill_20261009 \
 --manifest "$PERTURB_SKILL_OUTPUT_JOB/run_manifest.json" --shards "$SHARDS" \
 --shard-index "$PART" --output "$PERTURB_SKILL_OUTPUT_JOB/probe"
"$ROOT/.venv/bin/python" - "$PERTURB_SKILL_OUTPUT_JOB" "$STARTUP" <<'CONTRACT'
from pathlib import Path
import hashlib,json,sys
out=Path(sys.argv[1]);startup=sys.argv[2]=='1'
rows=[json.loads(l) for l in (out/'probe/episodes.jsonl').read_text().splitlines() if l.strip()]
if not rows or any(r.get('infrastructure_failure') or r.get('raised_error') for r in rows):
    raise SystemExit('startup_or_runtime_error: inspect preserved episodes ledger')
if startup:
    if len(rows)!=1:raise SystemExit('startup requires exactly one attempted case')
    row=rows[0];stages=[*row.get('setup',[]),*([row['first_attempt']] if row.get('first_attempt') else [])]
    controls=sum(max(s.get('executed_actions',0),s.get('receipt',{}).get('sim_steps_used',0)) for s in stages)
    if controls<=0:raise SystemExit('startup requires actually executed physical controls')
    plan=json.loads((out/'run_manifest.json').read_text())
    contract={**plan['launcher_identity'],'status':'pass','case_name':row['case']['name'],
              'physical_controls':controls,'startup_is_part_of_selection':True,
              'episodes':{'path':str(out/'probe/episodes.jsonl'),
                          'sha256':hashlib.sha256((out/'probe/episodes.jsonl').read_bytes()).hexdigest()}}
    (out/'startup_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
CONTRACT
