"""Summarize only explicitly captured place-selection evidence."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_entity(entity):
    if entity is None:
        return None
    keys = ("id", "name", "visible", "source_step", "src", "geometry", "part_of", "xyz", "lower", "upper")
    return {key: entity.get(key) for key in keys}


def analyze(root, report_dir, manifest_path):
    report = json.loads((report_dir / "report.json").read_text())
    audit = json.loads((report_dir / "strict_setup_release_and_verifier_audit.json").read_text())
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) == audit["manifest_sha256"]
    base_path = report_dir / "preparation/base_config.json"
    assert sha(base_path) == manifest["base_config"]["sha256"]
    base = json.loads(base_path.read_text())
    by_case = {row["case"]: row for row in audit["records"]}
    setups, binding, missing_frames = [], [], []
    confusion, reasons, physical_failures = Counter(), Counter(), Counter()
    for ref in report["ledgers"]:
        path = root / Path(ref["path"]).relative_to(REMOTE_ROOT)
        assert sha(path) == ref["sha256"]
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            raw = json.loads(line)
            case = raw["case"]
            result = by_case[case["name"]]
            stage = (raw.get("setup") or [{}])[-1]
            receipt = stage.get("receipt", {})
            truth = stage.get("private_hold_truth_v2") or {}
            checks = truth.get("checks", [])
            public, private = receipt.get("grasp_verified"), truth.get("success")
            assert isinstance(public, bool) and isinstance(private, bool)
            confusion["TP" if public and private else "FP" if public else "FN" if private else "TN"] += 1
            config = {**base, **manifest["conditions"][case["condition"]].get("overrides", {})}
            observed = {
                "case": case["name"], "group": result["group"], "ledger": ref["path"], "line": line_no,
                "registered_mode": case["setup"][-1]["mode"], "observed_mode": receipt.get("mode"),
                "category_profile_enabled": config.get("grasp_category_profiles_v1", False),
                "public_grasp_verified": public, "private_hold_truth_v2": private,
                "legacy_setup_truth": stage.get("private_true_sustained_grasp"),
                "chunks": receipt.get("chunks"), "stop": receipt.get("stop"),
                "failure_reason": receipt.get("failure_reason"), "failure_detail": receipt.get("failure_detail"),
                "opening_m": receipt.get("gripper_opening"), "public_z_rise_cm": receipt.get("measured_z_rise_cm"),
                "private_min_clearance_m": truth.get("min_clearance_m"),
                "private_required_clearance_m": truth.get("required_clearance_m"),
                "private_samples": len(checks), "finger_contact_samples": sum(row.get("finger_contact") is True for row in checks),
                "non_gripper_support_samples": sum(row.get("touching_non_gripper_support") is True for row in checks),
                "approach_target_xyz": receipt.get("approach_target_xyz"),
                "approach_residual_m": receipt.get("approach_residual_m"),
                "contact_standoff_m": receipt.get("contact_policy_standoff_m"),
                "approach_acceptance_m": receipt.get("approach_acceptance_m"),
            }
            setups.append(observed)
            if raw["status"] == "setup_grasp_not_publicly_verified":
                reason = receipt.get("failure_reason") or receipt.get("stop") or "not_recorded"
                reasons[reason] += 1
                if private:
                    physical_failures["public_false_negative_true_hold"] += 1
                elif not any(row.get("finger_contact") for row in checks):
                    physical_failures["no_finger_contact_at_private_endpoint"] += 1
                else:
                    physical_failures["finger_contact_without_sustained_clearance"] += 1
            first = raw.get("first_attempt") or {}
            first_receipt = first.get("receipt", {})
            reason = first_receipt.get("failure_reason")
            if raw["status"] == "first_attempt_public_binding_missing" or reason in {
                "selected_instance_not_uniquely_measured", "selected_support_surface_not_uniquely_measured"
            }:
                observation = raw.get("public_at_stop") or first.get("public_before") or {}
                entities = observation.get("entities", [])
                # Record all relevant public peer measurements, including missing peers.
                relevant = [compact_entity(entity) for entity in entities
                            if any(word in entity.get("name", "") for word in ("bowl", "cabinet", "drawer"))]
                binding.append({"case": case["name"], "group": result["group"], "ledger": ref["path"], "line": line_no,
                    "classification": result["exclusive_classification"], "error": raw.get("binding_error") or reason,
                    "selected": first.get("selected"), "public_entities": relevant,
                    "public_robot": observation.get("robot"), "private_setup_true": private})
            if result["first_physically_executed"] and first_receipt.get("place_verified") is None:
                value = first.get("verification_measurements") or {}
                telemetry = (value.get("release_reverification") or {}).get("release_history") or {}
                missing_frames.append({"case": case["name"], "group": result["group"], "ledger": ref["path"], "line": line_no,
                    "first": compact_entity(value.get("first")), "second": compact_entity(value.get("second")),
                    "target": compact_entity(value.get("target")), "eef_xyz": value.get("eef_xyz"),
                    "opening_m": value.get("opening"), "interval_s": value.get("interval_s"),
                    "same_action_open_events": len(telemetry.get("open_events", [])),
                    "actual_vla_chunks": len(telemetry.get("chunks", [])),
                    "private_endpoint_satisfied": result["private_after"], "public_verdict": None,
                    "reason": first_receipt.get("verification_reason"),
                    "fresh_frames": (value.get("release_reverification") or {}).get("fresh_frames")})
    assert len(setups) == 40 and len(binding) == 6 and len(missing_frames) == 5
    assert sum(not row["public_grasp_verified"] for row in setups) == 12
    assert all(not row["category_profile_enabled"] for row in setups)
    return {"job_id": audit["job_id"], "registered_cases": 40,
        "report_sha256": sha(report_dir / "report.json"),
        "audit_sha256": sha(report_dir / "strict_setup_release_and_verifier_audit.json"),
        "manifest": {"path": str(manifest_path), "sha256": sha(manifest_path)},
        "base_config": {"original_path": manifest["base_config"]["path"], "captured_path": str(base_path), "sha256": sha(base_path)},
        "setup_public_private_confusion": dict(confusion), "setup_unverified_receipt_reasons": dict(reasons),
        "setup_unverified_endpoint_categories": dict(physical_failures),
        "binding_failure_counts": dict(Counter(row["classification"] for row in binding)),
        "setup_records": setups, "binding_failure_records": binding, "public_missing_frame_records": missing_frames,
        "source_sha256": sha(Path(__file__)), "new_physical_trials": 0, "new_training_rows": 0,
        "scope": "saved diagnostic endpoints and public RGB-D only; no label changed; no confirmation qualification"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.root.resolve(), args.report_dir.resolve(), args.manifest.resolve())
    output = args.report_dir / "setup_and_missing_frame_diagnosis.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"path": str(output), "sha256": sha(output),
        "setup_confusion": result["setup_public_private_confusion"],
        "setup_unverified_reasons": result["setup_unverified_receipt_reasons"],
        "setup_endpoint_categories": result["setup_unverified_endpoint_categories"],
        "binding_failures": result["binding_failure_counts"], "missing_public_frames": len(result["public_missing_frame_records"])}))


if __name__ == "__main__":
    main()
