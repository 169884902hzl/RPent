"""CPU audit of explicitly named original-skill smoke manifests and ledgers."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from scripts.audit_v5_skill501_closed_smokes import skill_record
from scripts.probe_v5_skill501_original import sha
from scripts.summarize_v5_skill501_original import summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.manifest, args.ledger)
    rows = []
    for path in args.ledger:
        raw = path.read_bytes()
        if not raw.endswith(b"\n"):
            raise ValueError("incomplete ledger tail: " + str(path))
        rows.extend(json.loads(line) for line in raw.splitlines() if line.strip())
    records = [skill_record(row) for row in rows]
    frame_audits = []
    for row in records:
        frames = row["contact_evidence"].get("independent_grasp_frame_observations", [])
        contradictions = []
        per_view_counts = Counter()
        for index, frame in enumerate(frames):
            for camera, view in frame.get("per_view", {}).items():
                verdict = view.get("verified")
                per_view_counts[f"{camera}:{verdict}:{view.get('reason')}"] += 1
                rejected = [key for key, value in view.get("conditions", {}).items() if value is False]
                unknown = [key for key, value in view.get("conditions", {}).items() if value is None]
                if verdict is True and (rejected or unknown):
                    contradictions.append({"frame_index": index, "camera": camera, "saved_verified": verdict,
                        "saved_conditions": view["conditions"], "rejected_conditions": rejected,
                        "unknown_conditions": unknown, "measured_lower_lift_m": view.get("lower_lift_m"),
                        "original_support_clearance_m": view.get("original_support_clearance_m")})
        sync = row["contact_evidence"].get("private_frame_sync", {})
        sync_samples = sync.get("samples", [])
        rawpoint_files = 0
        for sample in sync_samples:
            if "metadata" in sample and sha(sample["metadata"]["path"]) != sample["metadata"]["sha256"]:
                raise ValueError("private-frame-sync metadata SHA mismatch")
            for view in sample["per_view"].values():
                points = view.get("points")
                if points is not None:
                    if sha(points["path"]) != points["sha256"]:
                        raise ValueError("private-frame-sync raw cloud SHA mismatch")
                    rawpoint_files += 1
        frame_audits.append({"case": row["case"], "frames": len(frames),
            "frame_verdict_counts": dict(Counter(f"{frame.get('verified')}:{frame.get('reason')}" for frame in frames)),
            "per_view_counts": dict(per_view_counts), "contradictions": contradictions,
            "saved_contradiction_count": len(contradictions),
            "sync_sample_count": len(sync_samples), "sync_rawpoint_files_sha_checked": rawpoint_files,
            "sync_unsafe_physics_time_count": sum(sample.get("same_physics_time") is not True for sample in sync_samples),
            "scope": "saved frame verdicts audited without replacing any runtime receipt or later physical label"})
    report.update(job=args.job, source_snapshot=str(args.source),
        source_sha256={name: sha(args.source / name) for name in
            ("scripts/probe_v5_skill501_original.py", "robots/libero/v5_runtime.py",
             "robots/libero/v5_grasp_measurement.py", "robots/libero/v5_fixture_parts.py",
             "robots/libero/v5_verification.py")},
        summary_source={"path": str(Path(__file__)), "sha256": sha(__file__), "python": sys.executable},
        records=records, frame_audits=frame_audits,
        infra_or_execution_errors=sum(bool(row["raised_error"] or row["receipt"].get("error")
            or row["receipt"].get("verification") == "execution_error") for row in records),
        fixture_physical_classes=dict(Counter(row["physical_class"] for row in records if row["kind"] == "articulate")),
        raw_choices_sha_checked=len(rows), raw_choices_sha_mismatches=0,
        private_sync_scope="read-only calibration samples at existing measured frames; not confirmation or training")
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    lines = [f"# Original-skill development smoke {args.job}", "",
             f"Complete: {report['complete']}. Recorded: {len(rows)}. Infrastructure/execution errors: {report['infra_or_execution_errors']}.",
             "No new physical trials, training rows, or qualification.", "",
             "| Case | Official target before → after | True sustained grasp during / at end | Public verdict | Actual first actions |", "|---|---|---|---|---|"]
    for row in records:
        receipt = row["receipt"]
        verdict = receipt.get("articulate_verified", receipt.get("place_verified", receipt.get("grasp_verified")))
        lines.append(f"| {row['case']} | {row['private_before']} → {row['private_after']} | {row['grasp_during_skill']} / {row['grasp_at_end']} | {verdict} ({receipt.get('verification')}) | {row['actions']} |")
    lines += ["", "| Case | Saved independent frames | Saved-condition contradictions | Same-frame private samples |", "|---|---|---|---|"]
    for row in frame_audits:
        lines.append(f"| {row['case']} | {row['frames']} | {row['saved_contradiction_count']} | {row['sync_sample_count']} |")
    lines += ["", "Single-frame witnesses are distinct from runtime two-frame grasp verdicts. A later successful release does not undo a prior sustained grasp.",
              "Saved false/null evidence is retained. Contradictions expose the old verifier logic; these records are not silently relabeled.",
              f"Report SHA256: {sha(output)}. Exact raw paths, hashes, conditions and requested-mode audit are in report.json."]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"complete": report["complete"], "recorded": len(rows), "errors": report["infra_or_execution_errors"],
        "output": str(output), "sha256": sha(output), "contradictions": sum(row["saved_contradiction_count"] for row in frame_audits),
        "fixture_classes": report["fixture_physical_classes"]}))


if __name__ == "__main__":
    main()
