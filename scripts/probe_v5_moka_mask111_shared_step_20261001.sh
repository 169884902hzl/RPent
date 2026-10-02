#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_wrist103_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import json,os,re,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);shared=Path(os.environ['LIBERO_SHARED_OUTPUT'])
endpoint=re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',(shared/'shared_sam3.log').read_text())[0]
out=root/'results/harness_v5/moka_mask111_20261001'/f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}'
argv=[sys.executable,str(root/'runtime_launchers/probe_v5_moka_mask111_20261001.py'),'--manifest',str(out.parent/'manifest.json'),'--endpoint',endpoint,'--output',str(out)]
print(json.dumps({'argv':argv,'scope':'reuse own SAM; no new GPU allocation, physics, or labels'}),flush=True)
subprocess.run(argv,check=True)
PY
