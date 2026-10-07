"""CPU preparation and same-launcher checks; no sbatch or simulator startup."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE = ROOT / "results/harness_v5/temporal_control580_capture_CPU_20261007"
PACKET = BASE / "r3"
OLD = BASE / "r2/capture_manifest.json"
SOURCE = BASE / "r3_prepare_source.py"


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def main():
    old_identity = identity(OLD)
    assert old_identity["sha256"] == "1ed09b14fa58d6309b4aef79fa59090eeb6d49eb29c5e27b3693e7840552fc2f"
    assert identity(SOURCE)["sha256"] == "09a9ec4123c845d0d92eda5f3603dd11d0aca7431854b1f6d78bc3cd6c9896ca"
    old = json.loads(OLD.read_text())
    pinned_old_sources = [identity(item["path"]) for item in old["source_files"]]
    for actual, expected in zip(pinned_old_sources, old["source_files"]):
        assert actual == expected
    selection, sampling = old["selection_manifest"], old["sampling_manifest"]
    command = [str(ROOT / ".venv/bin/python"), str(SOURCE),
        "--selection-manifest", selection["path"], "--selection-manifest-sha256", selection["sha256"],
        "--sampling-manifest", sampling["path"], "--sampling-manifest-sha256", sampling["sha256"],
        "--output", str(PACKET), "--physical-output", str(ROOT / "results/harness_v5/temporal_control580_original_r3_20261008"),
        "--preserve-pre-off-contact"]
    prepared = subprocess.run(command, text=True, capture_output=True, check=True)
    report = json.loads(prepared.stdout)
    (PACKET / "prepare_stdout.json").write_text(prepared.stdout)
    (PACKET / "prepare_stderr.log").write_text(prepared.stderr)
    plan = json.loads((PACKET / "capture_manifest.json").read_text())
    assert plan["cases"] == old["cases"] and plan["fixed_on_chunks"] == plan["fixed_off_chunks"] == 160
    checks = []
    for index in range(3):
        env = dict(os.environ, CONTROL_CAPTURE_PREFLIGHT_ONLY="1", SLURM_ARRAY_JOB_ID="CPU_r3_contact",
                   SLURM_ARRAY_TASK_ID=str(index))
        run = subprocess.run(["bash", str(PACKET / "run_capture.sbatch")], env=env, text=True, capture_output=True)
        stdout, stderr = PACKET / f"preflight_part{index}_stdout.log", PACKET / f"preflight_part{index}_stderr.log"
        stdout.write_text(run.stdout)
        stderr.write_text(run.stderr)
        if run.returncode:
            raise RuntimeError(f"same-launcher CPU preflight {index} failed: {run.stderr}")
        evidence_path = Path(plan["output_root"]) / "probe_jobCPU_r3_contact" / f"preflight_part{index}.json"
        evidence = json.loads(evidence_path.read_text())
        assert evidence["passed"] and evidence["raw_state_sha256"] == plan["cases"][index]["state_sha256"]
        assert evidence["simulator_started"] is False and evidence["gpu_services_started"] is False
        checks.append({"shard_index": index, "returncode": run.returncode,
            "raw_state_sha256": evidence["raw_state_sha256"], "source_files_checked": evidence["source_files_checked"],
            "stdout": identity(stdout), "stderr": identity(stderr), "evidence": identity(evidence_path)})
    assert identity(OLD) == old_identity
    assert all(identity(ref["path"]) == ref for ref in pinned_old_sources)
    receipt = {"version": "control580-r3-contact-same-launcher-CPU/1", "source_commit": "740f24d0d3cf3f11030458e6495f26aa80170f23",
        "preparation_command": command, "preparation": report, "manifest": identity(PACKET / "capture_manifest.json"),
        "checks": checks, "old_r2_manifest": old_identity, "old_r2_pinned_sources_unchanged": True,
        "GPU_submitted": False, "physical_run_verified": False, "confirmation": False,
        "physical_smoke_pending": True, "first_physical_submission": ["sbatch", "--array=0-0%1", str(PACKET / "run_capture.sbatch")],
        "remaining_submission_after_real_first_request": ["sbatch", "--array=1-2%2", str(PACKET / "run_capture.sbatch")]}
    (PACKET / "same_launcher_CPU_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": identity(PACKET / "same_launcher_CPU_receipt.json"), "result": receipt}, indent=2))


if __name__ == "__main__":
    main()
