#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=130G
#SBATCH --time=02:00:00
#SBATCH --nice=10000
#SBATCH --job-name=libero-motion-prefix
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${MOTION_SOURCE:?absolute source required}
PREP=${MOTION_PREP:?absolute preparation required}
OUT=${MOTION_OUTPUT:?new absolute output required}
STARTUP=${MOTION_STARTUP:-0}
CONTRACT=${MOTION_STARTUP_CONTRACT:-}
export PYTHONPATH="$SOURCE" LIBERO_TYPE=standard LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export LIBEROPRO_DATASET_PATH=/public/home/sunyihan/liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl PYTHONDONTWRITEBYTECODE=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$SOURCE" "$PREP" "$0" <<'CHECK'
import hashlib,json,sys
from pathlib import Path
source,prep,launcher=map(Path,sys.argv[1:])
x=json.loads((prep/'manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert source.is_absolute() and prep.is_absolute() and x['source_path']==str(source)
assert x['training_allowed'] is False and x['confirmation'] is False
assert sha(launcher)==x['launcher']['sha256']
for r in x['inputs']+x['source_files']:
 p=Path(r['path']);assert p.is_absolute() and p.is_file() and sha(p)==r['sha256'],str(p)
for c in x['cases']:
 config=json.loads(Path(c['config']).read_text())
 assert config['libero_type']=='standard' and 0<=config['seed']<5
for p in [Path(x['choice_package']),Path('/public/home/sunyihan/rpent_libero_eval/assets/pi05'),
          Path('/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt')]:
 assert p.exists(),str(p)
import harness_v5_eval,typed_choice_eval
assert Path(harness_v5_eval.__file__).resolve()==source/'harness_v5_eval.py'
assert Path(typed_choice_eval.__file__).resolve()==source/'typed_choice_eval.py'
from robots.libero.v5_env_client import V5SkillEnvClient
from robots.libero.v5_runtime import MeasuredScene,V5Executor
print('same-source CPU path/import preflight passed')
CHECK
if [[ "${MOTION_CPU_ONLY:-0}" == 1 ]]; then exit 0; fi
"$ROOT/.venv/bin/python" - "$PREP" "$OUT" "$STARTUP" "$CONTRACT" <<'PLAN'
import hashlib,json,sys
from pathlib import Path
prep,out=map(Path,sys.argv[1:3]);startup,contract=sys.argv[3:]
x=json.loads((prep/'manifest.json').read_text())
cases=x['cases'][:1] if startup=='1' else x['cases'][1:]
if startup!='1':
 c=json.loads(Path(contract).read_text())
 assert c['status']=='pass' and c['manifest_sha256']==hashlib.sha256((prep/'manifest.json').read_bytes()).hexdigest()
 assert c['source_path']==x['source_path'] and c['first_case']==x['cases'][0]['name']
 assert c['physical_actions']>0
assert cases
out.mkdir(parents=True,exist_ok=False)
(out/'runtime_manifest.json').write_text(json.dumps({**x,'cases':cases},indent=2)+'\n')
PLAN
"$ROOT/.venv/bin/python" -u "$SOURCE/scripts/replay_v5_original_motion.py" \
 --manifest "$OUT/runtime_manifest.json" --output "$OUT/probe"
"$ROOT/.venv/bin/python" - "$PREP" "$OUT" "$STARTUP" <<'RESULT'
import hashlib,json,sys
from pathlib import Path
prep,out=map(Path,sys.argv[1:3]);startup=sys.argv[3]=='1'
report=json.loads((out/'probe/report.json').read_text())
assert report['cases']
physical=0
for c in report['cases']:
 assert c['result'].get('status') not in ('startup','startup_error') and c['diagnostic_outcome']!='runtime_error',c
 p=Path(c['choices']['path'])
 for line in p.read_text().splitlines():
  r=json.loads(line)
  physical+=sum(m.get('steps_used',0)+m.get('executed_action_count',0) for m in r.get('motion_evidence',[]))
  physical+=int(r.get('receipt',{}).get('chunks',0) or 0)
assert physical>0,'no executed physical actions'
if startup:
 x=json.loads((prep/'manifest.json').read_text())
 assert len(report['cases'])==1
 c={'status':'pass','source_path':x['source_path'],'first_case':x['cases'][0]['name'],
    'manifest_sha256':hashlib.sha256((prep/'manifest.json').read_bytes()).hexdigest(),
    'physical_actions':physical,'report':str(out/'probe/report.json')}
 (out/'startup_contract.json').write_text(json.dumps(c,indent=2)+'\n')
print(json.dumps({'physical_actions':physical,'cases':len(report['cases']),'startup':startup}))
RESULT
