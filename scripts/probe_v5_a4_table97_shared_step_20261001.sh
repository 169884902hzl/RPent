#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_table97_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" - "$ROOT" "$SOURCE" <<'PY'
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from harness_v5_eval import run_episode

root, source = map(Path, sys.argv[1:])
shared = Path(os.environ['LIBERO_SHARED_OUTPUT'])
endpoints = {name: re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
             (shared / f'shared_{name}.log').read_text())[0] for name in ('sam3', 'vla')}
manifest = source / 'configs/v5_a4_jev_d2_diagnostic40_20261001.json'
plan = json.loads(manifest.read_text())
out = root / 'results/harness_v5/a4_jev_table97_d2diag40_20261001' / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
(out / 'episodes').mkdir(parents=True, exist_ok=False)
pause = out.parent / 'PAUSE_REQUESTED'
summary = {'purpose': 'current table97 A4 development diagnosis; not frozen or final stop decision',
           'planned': 40, 'attempted': 0, 'correct_finish': 0, 'status': 'running',
           'shared_allocation': os.environ['SLURM_JOB_ID'], 'shared_endpoints': endpoints,
           'timing_scope': 'shared SAM/Pi0.5 queue; not an isolated latency comparison'}
with (out / 'episodes/episodes.jsonl').open('x') as ledger:
    for episode in plan['episodes']:
        if pause.exists():
            summary['status'] = 'yielded_between_episodes'
            break
        directory = out / 'episodes' / f'{episode["suite"]}_t{episode["task"]}_s{episode["seed"]}'
        args = argparse.Namespace(**episode, **plan['budget'], provider='jev', libero_type='pro',
                choice_package=Path('/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a'),
                choice_endpoint='http://10.10.223.2:18582', sam3_endpoint=endpoints['sam3'],
                vla_endpoint=endpoints['vla'], output_dir=directory, done_gated=False)
        try:
            result = run_episode(args)
        except Exception:
            if not (directory / 'result.json').exists():
                raise
            result = json.loads((directory / 'result.json').read_text())
        record = {'episode': episode, 'output_dir': str(directory), 'result': result}
        ledger.write(json.dumps(record) + '\n')
        ledger.flush()
        summary['attempted'] += 1
        summary['correct_finish'] += int(result.get('correct_finish', False))
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(record), flush=True)
    else:
        summary['status'] = 'completed'
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
if summary['status'] == 'completed':
    subprocess.run([sys.executable, str(source / 'scripts/summarize_v5_timing40_20261001.py'),
                    '--manifest', str(manifest), '--results', str(out)], check=True)
print(json.dumps({'output': str(out), 'summary': summary}))
PY
