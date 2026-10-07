"""Audit one explicit layout startup ledger without rerunning a physical trial."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(ref):
    actual = identity(ref["path"])
    if actual["sha256"] != ref["sha256"]:
        raise ValueError(f"Pinned input changed: {ref['path']}")
    return json.loads(Path(ref["path"]).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = read_pinned({"path": str(args.manifest), "sha256": args.manifest_sha256})
    rows = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError("This audit requires the one explicit startup row")
    row = rows[0]
    case = next(case for case in plan["cases"] if case["name"] == row["case"]["name"])
    registered = read_pinned(case["registered_layout_state"])
    contract = json.loads(args.contract.read_text())
    choices_path = Path(row["output_dir"]) / "choices.jsonl"
    choices = [json.loads(line) for line in choices_path.read_text().splitlines() if line.strip()]
    if len(choices) != 1:
        raise ValueError("The startup trial must have one top-level decision")
    choice = choices[0]
    raw = registered["rawstate"]
    raw_sha = hashlib.sha256(struct.pack(f"<{len(raw)}d", *raw)).hexdigest()
    reset = row["registered_reset_evidence"]
    actual_geometry = reset["restored_private_geometry"]
    prepared_geometry = registered["preparation_provenance"]["settled_geometry"]
    geometry_error = max(abs(value - actual_geometry[name]["xyz"][axis])
                         for name, xyz in prepared_geometry.items()
                         for axis, value in enumerate(xyz))
    controls = row["server_chunk_execution"]
    endpoint = row["public_receipt_before_private_metrology"].get("temporal_endpoint", {})
    context = choice["request"]["context"]
    forbidden = [value for value in ("sim_truth", "oracle.status", "moka_pot_1",
                                    "flat_stove_1_cook_region") if value in context]
    references = [*plan["source_snapshot"]["files"], plan["source_snapshot"]["archive"],
                  plan["producer"], *plan["producer_dependencies"],
                  *plan["preparation_inputs"]]
    for ref in references:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError(f"Pinned source or preparation changed: {ref['path']}")
    checks = {
        "case_matches_manifest": row["case"] == case,
        "contract_manifest_matches": contract["manifest_sha256"] == args.manifest_sha256,
        "contract_case_matches": contract["case_name"] == case["name"],
        "contract_launcher_matches": contract["launcher_sha256"] == plan["launcher_identity"]["sha256"],
        "rawstate_sha_matches": raw_sha == registered["state_sha256"] == case["state_sha256"],
        "settled_restored_sha_matches": reset["settled_state_sha256"] == reset["restored_state_sha256"] == raw_sha,
        "proposed_sha_matches": reset["proposed_state_sha256"] == registered["preparation_provenance"]["proposed_state_sha256"],
        "geometry_fingerprint_matches": reset["geometry_fingerprint"] == case["geometry_fingerprint"],
        "restoration_error_zero": reset["max_absolute_restore_error"] == 0,
        "restored_geometry_matches_preparation": geometry_error == 0,
        "restored_before_first_scene_perception": reset["restore_stage"] == "environment_reset_before_client_scene_and_first_perception",
        "sensor_and_controller_reset_recorded": reset["raw_sensor_observables_forced"] and reset["controller_goals_reset"],
        "private_control_disabled": not controls["private_joint_or_predicate_used_for_control"] and not reset["policy_has_rawstate_access"],
        "complete_physical_chunks": controls["requested_controls"] == controls["executed_controls"] > 0 and not controls["external_truncation"] and not controls["native_success_stops_chunk"],
        "no_infrastructure_failure": not row["case_had_infrastructure_failure"],
        "choices_sha_matches_ledger": identity(choices_path)["sha256"] == row["choices_sha256"],
        "state_text_has_no_private_symbols": not forbidden,
        "entity_lines_are_perception": all("src=perception" in line for line in context.splitlines() if line.startswith("e ")),
        "request_within_limits": choice["prompt_tokens"] <= 3072 and len(choice["request"]["options"]) <= 24,
    }
    report = {
        "analysis_role": "startup_integrity_audit_not_skill_qualification",
        "job": "4499_0", "case_name": case["name"],
        "inputs": {"manifest": identity(args.manifest), "ledger": identity(args.ledger),
                   "contract": identity(args.contract), "choices": identity(choices_path),
                   "registered_state": case["registered_layout_state"]},
        "producer": identity(__file__), "checks": checks,
        "all_integrity_checks_pass": all(checks.values()),
        "pinned_source_and_preparation_references_checked": len(references),
        "reset_evidence": reset,
        "max_restored_geometry_error_m": geometry_error,
        "request": {"prompt_tokens": choice["prompt_tokens"], "candidate_count": len(choice["request"]["options"]),
                    "selected_diagnostic_placeholder": choice["selected"],
                    "actual_executed_tool": row["first_receipt"]["tool"],
                    "instruction": choice["request"]["context"].splitlines()[0]},
        "physical_result": {
            "official_success_before": row["private_original_task_status_before"]["done"],
            "official_success_after": row["private_original_task_status_after"]["done"],
            "official_success": row["result"]["official_success"],
            "public_place_verified": row["public_placement_verdict"],
            "endpoint_version": endpoint.get("version"),
            "two_frame_verdicts": endpoint.get("strict6_verdicts"),
            "stability_controls": endpoint.get("actual_hold_controls"),
            "stability_interval_s": endpoint.get("interval_s"),
            "stop_reason": endpoint.get("stop_reason"),
            "wall_s": row["wall_s"], "complete_chunk_execution": controls,
            "true_sustained_grasp": row["true_sustained_grasp"],
            "fusion_measurements": row["result"]["fusion_measurements"],
        },
        "limitations": [
            "One complete original moka transfer trial, not a standalone grasp-confirmation trial.",
            "The source runner records a grasp diagnostic placeholder; the actual executed receipt is vla_subtask.",
            "Only one of 24 registered layout states executed; the remaining 23 were not audited as physical trials here.",
            "Generated layouts use previously used original bases, are not official unused states, and do not establish IID or the100 confirmation threshold.",
            "The runtime ledger records proposed SHA; proposed geometry is in preparation evidence rather than directly in the runtime ledger.",
            "All original preparation gaps and trial records remain unchanged.",
        ],
        "training_rows": 0, "qualification_claimed": False,
        "gpu_jobs_submitted_by_audit": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"report": identity(args.output), "pass": report["all_integrity_checks_pass"],
                      "checks": checks, "physical_result": report["physical_result"]}, indent=2))
    if not report["all_integrity_checks_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
