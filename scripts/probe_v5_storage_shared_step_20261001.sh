#!/usr/bin/env bash
# Reuse an owned allocation's SAM and VLA; create independent original envs.
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_storage67_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
source = Path.cwd()
shared = Path(os.environ["LIBERO_SHARED_OUTPUT"])
output = root / "results/harness_v5/storage_open67_physical5_20261001" / (
    f'step_{os.environ["SLURM_JOB_ID"]}_{os.environ["SLURM_STEP_ID"]}')
output.mkdir(parents=True, exist_ok=False)
endpoints = {}
for name in ("sam3", "vla"):
    matches = re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',
                         (shared / f"shared_{name}.log").read_text())
    if not matches:
        raise RuntimeError(f"owned shared {name} is not ready")
    endpoints[name] = matches[0]
identity = {
    "purpose": "original Long9 init0-4 development repair, no training rows",
    "source_commit": "9f73744", "allocation": os.environ["SLURM_JOB_ID"],
    "step": os.environ["SLURM_STEP_ID"], "shared": str(shared),
    "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                      for name in ("robots/libero/v5_oracle_server.py", "robots/libero/v5_branch_state.py",
                                   "robots/libero/v5_runtime.py", "harness_v5_eval.py")},
    "episodes": [],
}
(output / "identity.json").write_text(json.dumps(identity, indent=2))
for init in range(5):
    episode = output / f"libero_10_t9_s{init}"
    argv = [sys.executable, "-u", str(source / "harness_v5_eval.py"),
            "--libero-type", "standard", "--provider", "oracle", "--suite", "libero_10",
            "--task", "9", "--seed", str(init), "--sam3-endpoint", endpoints["sam3"],
            "--vla-endpoint", endpoints["vla"], "--max-decisions", "100", "--max-chunks", "80",
            "--max-episode-steps", "10000", "--choice-package",
            "/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a",
            "--output-dir", str(episode)]
    print(json.dumps({"argv": argv}), flush=True)
    with (output / f"init{init}.log").open("w") as log:
        status = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
    result_path = episode / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    identity["episodes"].append({"init": init, "returncode": status, "result": result})
    (output / "summary.json").write_text(json.dumps(identity, indent=2))
    print(json.dumps(identity["episodes"][-1]), flush=True)
if any(row["returncode"] for row in identity["episodes"]):
    raise SystemExit(1)
PY
