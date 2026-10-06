#!/usr/bin/env bash
# CPU-only explicit-file/state validation. Starts no environment or model service.
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${1:?absolute source_v5_runtime538_20261006 snapshot path required}"
[[ "$SOURCE" == /* && -d "$SOURCE" ]]
export PYTHONPATH="$SOURCE" PYTHONDONTWRITEBYTECODE=1 LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$SOURCE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

from scripts.v5_probe_preflight import load_pinned_manifest, pinned_file, validate_registered_states

source = Path(sys.argv[1]).resolve(strict=True)
required = (
    "harness_v5_eval.py", "scripts/probe_v5_grasp449_20261005.py",
    "scripts/probe_v5_skill501_original.py", "scripts/v5_probe_preflight.py",
    "robots/libero/v5_runtime.py", "robots/libero/v5_env_client.py",
    "robots/libero/v5_env_server.py", "robots/libero/v5_sam3_server.py",
    "robots/libero/v5_grasp_measurement.py", "robots/libero/v5_perception_geometry.py",
    "robots/libero/v5_state.py", "robots/libero/v5_grasp_truth.py",
    "robots/libero/v5_oracle_policy.py", "robots/libero/v5_oracle_server.py",
    "robots/libero/v5_branch_state.py", "robots/libero/v5_reset_seed.py",
    "robots/libero/v5_motion_diagnostics.py", "robots/libero/v5_termination.py",
    "robots/libero/v5_fixture_parts.py", "robots/libero/v5_action_effect.py",
    "robots/libero/v5_moka_queries.py", "robots/libero/v5_recovery.py",
)
for name in required:
    if not (source / name).is_file():
        raise ValueError(f"snapshot omitted required source: {name}")
for name, expected in (
    ("scripts/probe_v5_grasp449_20261005.py", "f6d082336fac5d2c2e1fe1a9823b9427106ecb36aae3f8ce912056bed67f09e8"),
    ("robots/libero/v5_grasp_measurement.py", "648731eb7f890cbf706f5ede18b3560559d36a8b11e2579e738c5e39c96fd607"),
):
    if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
        raise ValueError(f"final grasp source changed: {name}")

root = Path("/public/home/sunyihan/rpent_libero_eval/results/harness_v5")
registered = (
    ("box52", root / "grasp_infrastructure_repair_20261006/preparation2/box52.json", "f7f611b82f6db5d6ecc89bb5981605f730c5b8c17022ffa891a4d06693b4956c", 52),
    ("mug100", root / "grasp_infrastructure_repair_20261006/preparation2/mug100.json", "c6874c4ecd43a45be9a428121753f98d9b41dc60a91f6c51093071f3cf28859c", 100),
    ("pan100", root / "grasp_next_methods_20261006/preparation/pan_wrist_new_states.json", "d5091b678e980f73e37157a769c9f85f9846c3cd91dfd93dac26553567e6fb58", 100),
    ("moka300", root / "grasp_next_methods_20261006/preparation/moka_methods_selection.json", "5f9044d6236128de6900b7b8ed15c0e792db615e117a6affe6be6dfc96061daa", 300),
)
for label, path, expected, count in registered:
    pinned_file({"path": str(path), "sha256": expected}, label)
    absolute, plan, base = load_pinned_manifest(path)
    if len(plan["cases"]) != count or base["libero_type"] != "standard":
        raise ValueError(f"registered case count or original LIBERO contract changed: {label}")
    if label == "pan100":
        calibration_file = pinned_file(plan["robot_calibration_file"], "robot_calibration_file")
        calibration = json.loads(Path(calibration_file["path"]).read_text())
        if plan["conditions"]["pan_wrist_confirmation"]["overrides"]["grasp_measurement_calibration"] != calibration:
            raise ValueError("embedded pan calibration differs from its registered source")
        pinned_file(calibration["grip_site_geometry"]["xml"], "public_gripper_geometry")
    checked = validate_registered_states(plan["cases"])
    print(json.dumps({"group": label, "manifest": str(absolute), "manifest_sha256": expected,
        "source": str(source), "state_cases_checked": checked["state_hashes_checked"],
        "unique_states": len({case["state_sha256"] for case in plan["cases"]}),
        "files_checked": len(plan["preflight"]["files_checked"]),
        "cpu_preflight": "passed", "physics_started": False, "services_started": False}), flush=True)
PY
