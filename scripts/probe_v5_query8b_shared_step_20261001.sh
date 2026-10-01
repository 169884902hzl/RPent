#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_original_branch_state2_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
exec "$ROOT/.venv/bin/python" - "$ROOT" "$SOURCE" <<'PY'
import json, os, re, subprocess, sys
from pathlib import Path

root, source = map(Path, sys.argv[1:])
shared = root / 'results/harness_v5/original_training1_660_20261001/job2840_task0'
matches = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)', (shared/'shared_sam3.log').read_text())
if not matches:
    raise RuntimeError('existing SAM allocation is not ready')
out = root/'results/harness_v5/query8b_shared_step_20261001'/f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}'
out.mkdir(parents=True, exist_ok=False)
(out/'runtime_identity.json').write_text(json.dumps({'source': str(source), 'shared_allocation': os.environ['SLURM_JOB_ID'],
    'purpose': 'fixed original RGB segmentation diagnosis only; no model evaluation'}, indent=2)+'\n')
for name in ('chocolate', 'butter'):
    subprocess.run([sys.executable, str(source/'scripts/probe_v5_category_masks_20261001.py'),
        '--manifest', str(root/f'configs/v5_query8b_{name}_20261001.json'),
        '--checkpoint', str(root/'assets/sam3/sam3.pt'), '--sam-endpoint', matches[0],
        '--output', str(out/name)], check=True)
print(json.dumps({'output': str(out)}))
PY
