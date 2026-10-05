"""Inspect explicit original-task grasp trajectories without claiming truth."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_trial(row):
    """Keep transient contact observations separate from sustained metrology."""
    receipt = row["first_receipt"]
    samples = row["contact_samples"]
    final = row.get("final_private_contact") or {}
    lifted = [sample for sample in samples if sample.get("contact_and_lift_3cm") is True]
    stop = receipt.get("stop") or receipt.get("failure_reason") or receipt.get("verification")
    if row.get("raised_error") or receipt.get("verification") == "execution_error":
        reason = "infrastructure_or_execution_error"
    elif not row["grasp_attempted"]:
        reason = "grasp_not_attempted"
    elif stop in ("approach_not_reached", "waypoint_not_reached", "wrist_pose_not_reached"):
        reason = stop
    elif row["visual_verified"]:
        reason = "visual_verifier_passed_truth_not_established"
    elif lifted:
        reason = "visual_verifier_failed_after_transient_contact_and_lift"
    elif any(s.get("target_dual_contact") is True for s in samples):
        reason = "dual_contact_observed_without_3cm_body_lift"
    else:
        reason = "no_dual_contact_and_lift_observed"
    return {
        "case": row["case"], "provisional_failure_class": reason,
        "visual_verified": row["visual_verified"], "stop": stop,
        "ever_dual_contact_and_3cm_body_lift": bool(lifted),
        "final_dual_contact_and_3cm_body_lift": final.get("contact_and_lift_3cm"),
        "max_body_rise_m": max((s["private_z_rise_m"] for s in samples
                               if s.get("private_z_rise_m") is not None), default=None),
        "first_contact_and_lift_sample": lifted[0] if lifted else None,
        "visual_verification_checks": len(row["verification_samples"]),
        "chunks": row["chunks"], "prompt": row.get("contact_prompt"),
        "source_episode": row["output_dir"],
        "true_sustained_grasp": row.get("true_sustained_grasp"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    planned = {case["name"]: case for case in manifest["cases"]}
    records, seen, groups, sources = [], set(), defaultdict(Counter), []
    for ledger in args.ledger:
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for row in map(json.loads, ledger.read_text().splitlines()):
            case = row["case"]
            if case != planned.get(case["name"]) or case["name"] in seen:
                raise ValueError("unregistered or duplicated trial")
            seen.add(case["name"])
            record = inspect_trial(row)
            records.append(record)
            group = groups[case["condition"] + "/" + case["group"]]
            group["recorded"] += 1
            group[record["provisional_failure_class"]] += 1
            group["transient_dual_contact_and_lift"] += record["ever_dual_contact_and_3cm_body_lift"]
            group["visual_verified"] += record["visual_verified"]
            group["stop:" + str(record["stop"])] += 1
    report = {
        "scope": "original-task provisional failure diagnosis; no sustained-truth or model-score claim",
        "manifest": {"path": str(args.manifest), "sha256": sha(args.manifest)},
        "script_sha256": sha(Path(__file__)), "explicit_ledgers": sources,
        "recorded": len(records), "planned": len(planned), "complete": seen == planned.keys(),
        "by_condition_class": {key: dict(counts) for key, counts in groups.items()},
        "trials": records, "new_training_rows": 0,
        "limitations": ["Chunk-end observations can miss contacts between samples.",
                        "Transient dual contact and body-origin rise are not sustained-hold truth.",
                        "No verifier false-positive/negative rate is inferred from these proxies."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"recorded": len(records), "planned": len(planned),
                      "complete": report["complete"], "report_sha256": sha(args.output),
                      "by_condition_class": report["by_condition_class"]}))


if __name__ == "__main__":
    main()
