#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
cd "$ROOT/source_v5_storage67_20261001"
export PYTHONPATH="$PWD"
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
shared = Path(os.environ["LIBERO_SHARED_OUTPUT"])
endpoint = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
                      (shared / "shared_sam3.log").read_text())[0]
output = root / "results/harness_v5/milk_original_training69_20261001" / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
argv = [sys.executable, str(root / "runtime_launchers/probe_v5_milk69_20261001.py"),
        "--manifest", str(root / "results/harness_v5/milk_original_training69_20261001/manifest.json"),
        "--endpoint", endpoint, "--prompts", "orange milk carton", "milk carton",
        "red and white milk carton", "carton labeled Milk"]
for threshold in (0.5, 0.35):
    command = argv + ["--min-score", str(threshold), "--output", str(output / str(threshold))]
    print(json.dumps({"argv": command, "purpose": "all30 saved training frames, no physics or labels"}), flush=True)
    subprocess.run(command, check=True)
PY
