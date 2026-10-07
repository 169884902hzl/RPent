"""Run the pinned CPU launcher in eight shards; never submit or execute physics."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest_ref, contract_ref = identity(args.manifest), identity(args.contract)
    plan = json.loads(args.manifest.read_text())
    contract = json.loads(args.contract.read_text())
    launcher = Path(plan["launcher_identity"]["path"])
    if identity(launcher) != plan["launcher_identity"]:
        raise ValueError("Pinned launcher changed")
    if (contract["status"] != "pass" or contract["requested_controls"] <= 0
            or contract["manifest_sha256"] != manifest_ref["sha256"]
            or contract["launcher_sha256"] != identity(launcher)["sha256"]):
        raise ValueError("Real startup contract differs from launcher or manifest")
    completed = contract["case_name"]
    selected = [case for case in plan["cases"] if case["name"] != completed]
    if len(selected) != 23:
        raise ValueError("Only the one startup case may be excluded")
    for case in selected:
        reference = case["registered_layout_state"]
        if identity(reference["path"]) != reference:
            raise ValueError("Registered rawstate file changed")
        raw = json.loads(Path(reference["path"]).read_text())["rawstate"]
        digest = hashlib.sha256(struct.pack(f"<{len(raw)}d", *raw)).hexdigest()
        if digest != case["state_sha256"]:
            raise ValueError("Registered rawstate bytes changed")
    env = os.environ.copy()
    for key in ("MOKA_TRANSFER_PREFLIGHT_ONLY", "MOKA_TRANSFER_STARTUP_PREFLIGHT",
                "MOKA_TRANSFER_EXCLUDE_CASES_FILE", "MOKA_TRANSFER_EXCLUDE_CASE_NAME"):
        env.pop(key, None)
    env.update(MOKA_TRANSFER_SOURCE=plan["source_snapshot"]["path"],
               MOKA_TRANSFER_MANIFEST=str(args.manifest),
               MOKA_TRANSFER_MANIFEST_SHA=manifest_ref["sha256"],
               MOKA_TRANSFER_STARTUP_CONTRACT=str(args.contract),
               MOKA_TRANSFER_STARTUP_CONTRACT_SHA=contract_ref["sha256"],
               MOKA_TRANSFER_EXCLUDE_CASE_NAMES=completed)
    text = launcher.read_text()
    if text.count("\ncd /tmp\n") != 1:
        raise ValueError("Pinned launcher CPU prefix boundary changed")
    # Execute exactly the formal launcher's immutable checks, including the
    # real contract and exclusion guard, and stop before any runner invocation.
    prefix = text.split("\ncd /tmp\n", 1)[0] + "\ndeclare -p FORMAL_CASE_ARGS\n"
    result = subprocess.run(["bash", "-c", prefix, str(launcher)], env=env,
                            text=True, capture_output=True)
    (args.output / "formal_prefix.stdout.log").write_text(result.stdout)
    (args.output / "formal_prefix.stderr.log").write_text(result.stderr)
    if result.returncode or completed not in result.stdout:
        raise RuntimeError("Formal CPU prefix rejected contract or exclusion")

    def shard(index):
        shard_env = dict(env, MOKA_TRANSFER_PREFLIGHT_ONLY="1", SLURM_ARRAY_TASK_ID=str(index))
        result = subprocess.run(["bash", str(launcher)], env=shard_env,
                                text=True, capture_output=True)
        stdout = args.output / f"part{index}.stdout.json"
        stderr = args.output / f"part{index}.stderr.log"
        stdout.write_text(result.stdout)
        stderr.write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f"CPU launcher shard{index} failed, exit{result.returncode}")
        data = json.loads(result.stdout)
        if data["GPU_started"] or data["physics_executed"]:
            raise RuntimeError("CPU-only launcher unexpectedly executed physics or GPU")
        cases = selected[index::8]
        return {"shard_index": index, "CPU_exit_code": result.returncode,
                "CPU_rawstates_checked_before_exclusion": data["registered_layout_states_checked"],
                "CPU_report": identity(stdout), "stderr": identity(stderr),
                "formal_case_names_after_exclusion_then_sharding": [case["name"] for case in cases],
                "formal_rawstate_references": [case["registered_layout_state"] for case in cases],
                "formal_case_count": len(cases)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        shards = list(pool.map(shard, range(8)))
    report = {"status": "pass", "manifest": manifest_ref, "contract": contract_ref,
              "launcher": identity(launcher), "producer": identity(__file__),
              "formal_cpu_prefix_exit_code": result.returncode,
              "formal_cpu_prefix_stdout": identity(args.output / "formal_prefix.stdout.log"),
              "excluded_completed_case": completed,
              "formal_selected_case_count": sum(shard["formal_case_count"] for shard in shards),
              "CPU_preflight_rawstates_checked": sum(shard["CPU_rawstates_checked_before_exclusion"] for shard in shards),
              "shards": shards,
              "selection_order": "exclude case names before slicing filtered cases[index::8]",
              "selection_order_source": identity(Path(plan["source_snapshot"]["path"]) / "scripts/probe_v5_grasp449_20261005.py"),
              "CPU_preflight_note": "Pinned preflight checks all24 unfiltered states; explicit formal23 mapping and rawstate digests checked separately.",
              "GPU_started": False, "physics_executed": False, "new_trials": 0, "jobs_submitted": 0}
    output = args.output / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(output), "status": report["status"],
                      "formal_selected": report["formal_selected_case_count"],
                      "per_shard": [shard["formal_case_count"] for shard in shards],
                      "excluded": completed, "physics_executed": False}, indent=2))


if __name__ == "__main__":
    main()
