#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
cd "$LIBERO_SOURCE"
export PYTHONPATH="$LIBERO_SOURCE"
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
shared = Path(os.environ['LIBERO_SHARED_OUTPUT'])
endpoint = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
    (shared / 'shared_sam3.log').read_text())[0]
out = root / 'results/harness_v5' / os.environ['LIBERO_OUTPUT_GROUP'] / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
subprocess.run([sys.executable,
    str(Path(os.environ['LIBERO_SOURCE']) / 'scripts/probe_v5_category_masks_20261001.py'),
    '--manifest', os.environ['LIBERO_MANIFEST'], '--sam-endpoint', endpoint,
    '--checkpoint', str(root / 'assets/sam3/sam3.pt'), '--output', str(out)], check=True)
print(json.dumps({'output': str(out)}))
PY
