#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_white_mug87_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
exec "$ROOT/.venv/bin/python" - "$ROOT" "$SOURCE" <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root, source = map(Path, sys.argv[1:])
shared = Path(os.environ['LIBERO_SHARED_OUTPUT'])
matches = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
                     (shared / 'shared_sam3.log').read_text())
if not matches:
    raise RuntimeError('active own SAM allocation is not ready')
out = root / 'results/harness_v5/white_mug_saved_cohort87_20261001' / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
argv = [sys.executable, str(source / 'scripts/probe_v5_package_segmentation_cohort_20261001.py'),
        '--manifest', str(root / 'results/harness_v5/white_mug_saved_cohort87_20261001/manifest.json'),
        '--endpoint', matches[0], '--output', str(out)]
print(json.dumps({'argv': argv, 'shared_allocation': os.environ['SLURM_JOB_ID'],
                  'purpose': 'ten complete original saved RGB frames; no physics or labels'}), flush=True)
subprocess.run(argv, check=True)
PY
