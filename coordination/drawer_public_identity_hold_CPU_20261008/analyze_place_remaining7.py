"""Audit only the explicitly registered placement jobs and public trace files."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def reference(path: Path) -> dict:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref: dict) -> Path:
    path = Path(ref["path"])
    if reference(path)["sha256"] != ref["sha256"]:
        raise ValueError(f"registered evidence changed: {path}")
    return path


def public_trace(attempt: dict) -> dict:
    index = Path(attempt["output_dir"]) / "place_trace_index.jsonl"
    if not index.exists():
        return {"index": None, "frames": [], "checked_files": []}
    refs = [json.loads(line) for line in index.read_text().splitlines() if line]
    checked_files = {}
    frames = []
    for ref in refs:
        frame = json.loads(checked(ref).read_text())
        checked_files[ref["path"]] = ref
        for camera in frame["cameras"].values():
            for key in ("rgb", "world_xyz", "camera_metadata"):
                if camera.get(key):
                    checked(camera[key])
                    checked_files[camera[key]["path"]] = camera[key]
        for entity in frame["entities"].values():
            evidence = entity["perception_evidence"]
            child_refs = list(evidence.get("sam_mask_files", {}).values())
            if entity.get("fused_cloud"):
                child_refs.append(entity["fused_cloud"])
            child_refs.extend(view["cloud"] for view in entity["per_view"].values() if view.get("cloud"))
            for child in child_refs:
                checked(child)
                checked_files[child["path"]] = child
        frames.append(
            {
                "reference": ref,
                "phase": frame["phase"],
                "source_step": frame["source_step"],
                "action": frame.get("action"),
                "robot": frame["robot"],
                "held_offset_m": frame.get("held_offset_m"),
                "entities": {
                    eid: {
                        "current": value["current"],
                        "eef_minus_current_measured_midpoint_m": value.get("eef_minus_current_measured_midpoint_m"),
                        "source_cameras": value["perception_evidence"].get("source_cameras", []),
                    }
                    for eid, value in frame["entities"].items()
                },
            }
        )
    return {"index": reference(index), "frames": frames, "checked_files": list(checked_files.values())}


def inspect_job(job: dict) -> dict:
    result = {key: job[key] for key in ("job_id", "case_number", "case_name", "episode", "condition", "output_dir")}
    ledger = Path(job["episodes_file"])
    if not ledger.exists():
        result.update(readiness="episodes_not_present", model_result=None)
        return result
    content = ledger.read_text()
    if not content.strip() or not content.endswith("\n"):
        result.update(readiness="episodes_write_in_progress", model_result=None)
        return result
    rows = [json.loads(line) for line in content.splitlines() if line]
    if len(rows) != 1:
        raise ValueError(f"one-case job must have exactly one completed row: {ledger}")
    row = rows[0]
    if row["case"]["name"] != job["case_name"] or row["case"]["state_sha256"] != job["state_sha256"]:
        raise ValueError(f"result differs from registered case: {ledger}")
    first = row.get("first_attempt")
    stage = first or {}
    motions = stage.get("motion_evidence", [])
    controls = sum(int(motion.get("executed_action_count", motion.get("steps_used", 0))) for motion in motions)
    if first is not None and controls != first["executed_actions"]:
        raise ValueError(f"target execution counter differs: {ledger}")
    before = stage.get("private_before", {}).get("satisfied")
    after = stage.get("private_after", {}).get("satisfied")
    result.update(
        readiness="completed_record_present",
        episodes=reference(ledger),
        status=row["status"],
        infrastructure_failure=row["infrastructure_failure"],
        case_had_infrastructure_failure=row["case_had_infrastructure_failure"],
        case_wall_s=row["case_wall_s"],
        setup_publicly_verified=[step.get("receipt", {}).get("grasp_verified") for step in row.get("setup", []) if step.get("phase") == "setup"],
        setup_private_sustained_grasp=[step.get("private_true_sustained_grasp") for step in row.get("setup", []) if "private_true_sustained_grasp" in step],
        target_present=first is not None,
        target_selected=stage.get("selected"),
        target_executed_controls=controls,
        target_vla_chunks=[motion["executed_action_count"] for motion in motions if motion.get("name") == "vla_act_chunk"],
        target_motion_counts=dict(Counter(motion.get("name", "unnamed") for motion in motions)),
        target_public_place_verified=stage.get("receipt", {}).get("place_verified"),
        target_receipt=stage.get("receipt"),
        private_before_satisfied=before,
        private_after_satisfied=after,
        target_newly_satisfied=bool(controls > 0 and before is False and after is True),
        target_already_satisfied_preserved=bool(controls > 0 and before is True and after is True),
        private_label_fields_used=["first_attempt.private_before.satisfied", "first_attempt.private_after.satisfied", "setup.private_true_sustained_grasp"],
        private_geometry_used=False,
        binding_error=row.get("binding_error"),
        target_controls_exclude_setup=True,
        public_attempts=[{"attempt": attempt, "public_trace": public_trace(attempt)} for attempt in row["attempts"]],
        qualification_authorized=False,
        old_results_changed=False,
        model_result=None,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text())
    checked(mapping["original_submission"])
    for job in mapping["jobs"]:
        checked(job["manifest"])
    cases = [inspect_job(job) for job in mapping["jobs"]]
    completed = [case for case in cases if case["readiness"] == "completed_record_present"]
    result = {
        "schema": "place-trace-remaining7-execution-audit/1",
        "mapping": reference(args.mapping),
        "registered_jobs": len(cases),
        "completed_records": len(completed),
        "source_commit": mapping["source_commit"],
        "cases": cases,
        "summary": {
            "statuses": dict(Counter(case["status"] for case in completed)),
            "target_executed": sum(case["target_executed_controls"] > 0 for case in completed),
            "newly_satisfied": sum(case["target_newly_satisfied"] for case in completed),
            "already_satisfied_preserved": sum(case["target_already_satisfied_preserved"] for case in completed),
            "infrastructure_failures": sum(case["infrastructure_failure"] for case in completed),
        },
        "qualification_authorized": False,
        "runtime_default_fixed": False,
        "runtime_scope": "current fragment canonicalization and extra drawer query enabled only in development trace context",
        "new_gpu_submissions": 0,
        "new_training_rows": 0,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError(f"immutable report already differs: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(json.dumps({"report": str(args.output), "sha256": reference(args.output)["sha256"], "completed_records": len(completed), "summary": result["summary"]}))


if __name__ == "__main__":
    main()
