# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Pin the existing twenty real-box cases to the current oracle source."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def identity(path: Path) -> dict:
    """Identify an existing artifact by its absolute path and bytes."""
    return {"path": str(path.resolve(strict=True)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    """Preflight the unchanged cases, optionally queueing their physical startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit-startup", action="store_true")
    args = parser.parse_args()
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    base = root / "coordination/bounded_skills_20261016"
    reports = base / "reports"
    prior = json.loads((reports / "original20_support_roundrobin_20261018_full_submission.json").read_text())
    source = Path(prior["snapshot"]).resolve(strict=True)
    launcher = source / "scripts/run_bounded_21f0744_20261017.sbatch"
    previous = root / "results/bounded_skills/feasibility_20261017/preparation/original20_manifest_real_box_r2_20261018.json"
    plan = json.loads(previous.read_text())
    cases = plan["cases"]
    assert len(cases) == 20 and {c["category"] for c in cases} == {"box_grab_place"}
    assert len({c["state_sha256"] for c in cases}) == 20
    assert not plan["training"] and not plan["confirmation"]
    plan["source_commit"] = prior["source_commit"]
    plan["previous_registration"] = identity(previous)
    manifest = previous.with_name("original20_manifest_real_box_support_r3_20261018.json")
    if manifest.exists():
        assert json.loads(manifest.read_text()) == plan
    else:
        manifest.write_text(json.dumps(plan, indent=2) + "\n")
    assert launcher.is_file()
    command = [str(root / ".venv/bin/python"), "-m", "scripts.v5_probe_preflight",
               "--manifest", str(manifest), "--shards", "1", "--shard-index", "0", "--states"]
    checked = subprocess.run(command, cwd=source, env={**os.environ, "PYTHONPATH": str(source),
        "LIBERO_TYPE": "standard", "LIBERO_CONFIG_PATH": str(root / "runtime_config"),
        "CUDA_VISIBLE_DEVICES": "", "OPENBLAS_NUM_THREADS": "1"}, text=True, capture_output=True)
    (reports / "real_box_support_r3_preflight_CPU_20261018.log").write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    preflight = {"manifest": identity(manifest), "prior_manifest": identity(previous),
        "source_commit": prior["source_commit"], "snapshot": str(source), "launcher": identity(launcher),
        "registered": len(cases), "case_contents_unchanged": cases == json.loads(previous.read_text())["cases"],
        "preflight_command": command, "preflight_exit": checked.returncode,
        "training": False, "confirmation": False, "gpu_used": False}
    (reports / "real_box_support_r3_preparation_CPU_20261018.json").write_text(json.dumps(preflight, indent=2) + "\n")
    if args.submit_startup:
        output = reports / "real_box_support_r3_20261018_startup_submission.json"
        assert not output.exists(), "Inspect the existing startup rather than submitting twice"
        arguments = ["sbatch", "--parsable", "--nodelist=node02", "--nice=500", "--array=0%1",
            "--dependency=afterany:" + prior["job"],
            "--export=ALL,SOURCE=" + str(source) + ",SOURCE_COMMIT=" + prior["source_commit"]
            + ",MANIFEST=" + str(manifest) + ",SHARD_COUNT=20,STARTUP=1,PAIR_LEGACY=0,PROBE_ARMS=oracle_k4",
            str(launcher)]
        job = subprocess.check_output(arguments, text=True).strip().split(";")[0]
        submission = {"job": job, "mode": "startup", "indices": [0], "arguments": arguments,
            "snapshot": str(source), "source_commit": prior["source_commit"], "manifest": identity(manifest),
            "formal_array_submitted": False, "physical_validation": "pending first physical request",
            "training": False, "confirmation": False,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        output.write_text(json.dumps(submission, indent=2) + "\n")
        print(json.dumps(submission))
    else:
        print(json.dumps(preflight))


if __name__ == "__main__":
    main()
