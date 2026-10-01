#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_visual_binding7_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import argparse, json, os, re, sys
from pathlib import Path
from harness_v5_eval import run_episode

root = Path(sys.argv[1])
shared = root/'results/harness_v5/original_training1_660_20261001/job2840_task0'
endpoints = {name: re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
    (shared/f'shared_{name}.log').read_text())[0] for name in ('sam3', 'vla')}
plan = json.loads((root/'configs/v5_visual_binding7_smoke4_20261001.json').read_text())
out = root/'results/harness_v5/binding7_shared_smoke4_20261001'/f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}'
out.mkdir(parents=True, exist_ok=False)
with (out/'episodes.jsonl').open('x') as ledger:
    for episode in plan['episodes']:
        directory = out/f'{episode["suite"]}_t{episode["task"]}_s{episode["seed"]}'
        args = argparse.Namespace(**episode, **plan['budget'], provider='oracle', libero_type='standard',
            choice_package=Path('/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a'),
            choice_endpoint=None, sam3_endpoint=endpoints['sam3'], vla_endpoint=endpoints['vla'],
            output_dir=directory, done_gated=False)
        try:
            result = run_episode(args)
        except Exception:
            if not (directory/'result.json').exists():
                raise
            result = json.loads((directory/'result.json').read_text())
        record = {'episode': episode, 'output_dir': str(directory), 'result': result}
        ledger.write(json.dumps(record)+'\n')
        ledger.flush()
        print(json.dumps(record), flush=True)
print(json.dumps({'output': str(out)}))
PY
