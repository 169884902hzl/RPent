#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_original_counterfactual1_20261001"
SHARED="$ROOT/results/harness_v5/original_training1_660_20261001/job2840_task0"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
exec "$ROOT/.venv/bin/python" - "$ROOT" "$SOURCE" "$SHARED" <<'PY'
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
root,source,shared=map(Path,sys.argv[1:])
endpoints={}
for name in ('sam3','vla'):
 matches=re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',(shared/f'shared_{name}.log').read_text())
 if not matches:raise RuntimeError(f'{name} is not ready')
 endpoints[name]=matches[0]
out=root/'results/harness_v5/cf_query8_shared_step_20261001'/f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}'
out.mkdir(parents=True,exist_ok=False)
(out/'runtime_identity.json').write_text(json.dumps({'shared_allocation':os.environ['SLURM_JOB_ID'],'shared_endpoints':endpoints,'source':'010a211 plus committed step launcher','limits':'development diagnosis; shared stochastic inference and timing are not controlled'},indent=2)+'\n')
for name in ('chocolate','butter','drawers','microwave'):
 subprocess.run([sys.executable,str(source/'scripts/probe_v5_category_masks_20261001.py'),
 '--manifest',str(root/f'configs/v5_query8_{name}_20261001.json'),'--checkpoint',str(root/'assets/sam3/sam3.pt'),
 '--sam-endpoint',endpoints['sam3'],'--output',str(out/name)],check=True)

from harness_v5_eval import run_episode
from robots.libero.v5_collection import OriginalCollection
registered=json.loads((root/'configs/v5_original_cf_registered1_20261001/manifest.json').read_text())
selected=next(v for v in registered['variants'] if v['goal']==['in','alphabet_soup_1','basket_1_contain_region'])
spec_path=Path(selected['spec']);spec=json.loads(spec_path.read_text())
original=json.loads((root/'source_v5_original_training1_retry1_20261001/configs/original_training1_registered_parts_v2_20261001/part_0.json').read_text())
episode=next(e for e in original['episodes'] if e['seed']==10)
episode={**episode,'counterfactual_spec':str(spec_path)}
args=argparse.Namespace(**episode,**original['budget'],provider='oracle',libero_type='standard',
 choice_package=Path('/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a'),
 choice_endpoint=None,sam3_endpoint=endpoints['sam3'],vla_endpoint=endpoints['vla'],
 output_dir=out/'libero_10_t0_s10_cf_alphabet',done_gated=True,instruction_override=spec['rewrites'][0])
config=json.loads((source/'configs/v5_original_training1_collection_20261001.json').read_text())
collection=OriginalCollection(config,args.output_dir,args)
try:
 result=run_episode(args,collection=collection)
except Exception:
 if not (args.output_dir/'result.json').exists():raise
 result=json.loads((args.output_dir/'result.json').read_text())
collection.finish(result)
record={'episode':episode,'output_dir':str(args.output_dir),'result':result}
(out/'episodes.jsonl').write_text(json.dumps(record)+'\n')
print(json.dumps({'output':str(out),'result':result}))
PY
