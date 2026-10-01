#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_original_branch_state2_20261001"
SHARED="$ROOT/results/harness_v5/original_training1_660_20261001/job2840_task0"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
exec "$ROOT/.venv/bin/python" - "$ROOT" "$SOURCE" "$SHARED" <<'PY'
import argparse,json,os,re,sys
from pathlib import Path
from harness_v5_eval import run_episode
from robots.libero.v5_collection import OriginalCollection
root,source,shared=map(Path,sys.argv[1:])
endpoints={name:re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',(shared/f'shared_{name}.log').read_text())[0] for name in ('sam3','vla')}
out=root/'results/harness_v5/branch_state2_shared_step_20261001'/f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}'
out.mkdir(parents=True,exist_ok=False)
base=root/'source_v5_original_training1_retry1_20261001'
original=json.loads((base/'configs/original_training1_registered_parts_v2_20261001/part_0.json').read_text())
episode=next(e for e in original['episodes'] if e['seed']==10)
config=json.loads((source/'configs/v5_original_training1_collection_20261001.json').read_text())
bank=json.loads(Path(config['wording_bank']).read_text())
variants=json.loads((root/'configs/v5_original_cf_registered1_20261001/manifest.json').read_text())['variants']
cf=next(v for v in variants if v['goal']==['in','alphabet_soup_1','basket_1_contain_region'])
with (out/'episodes.jsonl').open('x') as ledger:
 for variant in ('original','cf_alphabet'):
  item=dict(episode)
  if variant!='original':item['counterfactual_spec']=cf['spec']
  instruction=(bank['tasks']['libero_10/0']['rewrites'][0] if variant=='original' else json.loads(Path(cf['spec']).read_text())['rewrites'][0])
  args=argparse.Namespace(**item,**original['budget'],provider='oracle',libero_type='standard',choice_package=Path('/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a'),choice_endpoint=None,sam3_endpoint=endpoints['sam3'],vla_endpoint=endpoints['vla'],output_dir=out/variant,done_gated=True,instruction_override=instruction)
  collection=OriginalCollection(config,args.output_dir,args)
  try:result=run_episode(args,collection=collection)
  except Exception:
   if not (args.output_dir/'result.json').exists():raise
   result=json.loads((args.output_dir/'result.json').read_text())
  collection.finish(result)
  ledger.write(json.dumps({'episode':item,'output_dir':str(args.output_dir),'result':result})+'\n');ledger.flush()
  print(json.dumps({'variant':variant,'output':str(out),'result':result}),flush=True)
PY
