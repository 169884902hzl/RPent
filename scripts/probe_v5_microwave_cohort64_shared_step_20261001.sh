#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_bind57_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
shared = Path(os.environ['LIBERO_SHARED_OUTPUT'])
endpoints = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
                       (shared / 'shared_sam3.log').read_text())
if not endpoints:
    raise RuntimeError('active own SAM allocation is not ready')
output = root / 'results/harness_v5/microwave_saved_cohort64_20261001' / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
argv = [sys.executable, str(root / 'runtime_launchers/probe_v5_microwave_cohort64_20261001.py'),
        '--manifest', str(root / 'results/harness_v5/microwave_saved_cohort64_20261001/manifest.json'),
        '--endpoint', endpoints[0], '--output', str(output)]
print(json.dumps({'argv': argv, 'allocation': os.environ['SLURM_JOB_ID'],
                  'purpose': 'whole-fixture vs door class prompts, saved RGB-D only'}), flush=True)
subprocess.run(argv, check=True)
PY
