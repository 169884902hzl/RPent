"""Compare independently replayed measured counters and placement receipts."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_state import Candidate
from scripts.rerender_v5_format118_20261002 import entity, revised_receipt, robot_and_axes


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_jsonl(descriptor: dict) -> list[dict]:
    path = Path(descriptor["path"])
    if sha(path) != descriptor["sha256"]:
        raise ValueError(f"Declared input changed: {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def status_in(context: str) -> dict | None:
    match = re.search(r"^recovery no_progress_steps=(\d+) reperceive_cooldown=(\d+)$",
                      context, re.MULTILINE)
    if match is None:
        return None
    return dict(zip(("no_progress_steps", "reperceive_cooldown"), map(int, match.groups())))


def audit(index: dict) -> dict:
    """Audit only explicit closed traces; never alter receipts, scores or labels."""
    report = {"scope": "Measured runtime/re-render consistency, not a benchmark score or freeze",
              "new_training_rows": 0, "groups": []}
    for group in index["groups"]:
        counts, diffs, traces = Counter(), [], []
        for descriptor in group["traces"]:
            events = checked_jsonl(descriptor)
            traces.append(descriptor)
            raw, rounded = MeasuredRecovery(), MeasuredRecovery()
            for event in events:
                counts["decisions"] += 1
                location = {"trace": descriptor["path"], "decision": event["decision"]}
                before = status_in(event["request"]["context"])
                if before is not None:
                    counts["recorded_pre_recovery"] += 1
                    if raw.status() != before:
                        counts["raw_pre_recovery_mismatch"] += 1
                        diffs.append({**location, "kind": "raw_pre_recovery_mismatch",
                                      "recorded": before, "recomputed": raw.status()})
                snapshots = {"raw": [], "rounded": []}
                try:
                    for prefix in ("", "post_"):
                        opening, held, _ = robot_and_axes(event[prefix + "request"]["context"])
                        measured = [entity(e) for e in event[prefix + "measurements"]]
                        recorded = event.get(prefix + "robot_measurement") or {}
                        if "gripper_opening" not in recorded:
                            raise KeyError("full_precision_gripper_opening_missing")
                        snapshots["raw"].append(raw.snapshot(measured, held, recorded["gripper_opening"]))
                        snapshots["rounded"].append(rounded.snapshot(measured, held, opening))
                except (KeyError, ValueError) as error:
                    counts["recovery_missing_evidence"] += 1
                    diffs.append({**location, "kind": "recovery_missing_evidence", "error": str(error)})
                    # A missing transition invalidates subsequent replay counters.
                    break
                action = Candidate.from_text(event["receipt"].get("card_action") or event["selected"])
                raw.observe(action, *snapshots["raw"])
                rounded.observe(action, *snapshots["rounded"])
                if raw.status() != rounded.status():
                    counts["rounded_vs_raw_recovery_mismatch"] += 1
                    diffs.append({**location, "kind": "rounded_vs_raw_recovery_mismatch",
                                  "raw": raw.status(), "rounded": rounded.status(),
                                  "robot_before": event["robot_measurement"],
                                  "robot_after": event["post_robot_measurement"]})
                after = status_in(event["post_request"]["context"])
                if after is not None:
                    counts["recorded_post_recovery"] += 1
                    if raw.status() != after:
                        counts["raw_post_recovery_mismatch"] += 1
                        diffs.append({**location, "kind": "raw_post_recovery_mismatch",
                                      "recorded": after, "recomputed": raw.status()})
                receipt = event["receipt"]
                if receipt.get("tool") in ("place", "adjust_place"):
                    counts["placement_receipts"] += 1
                    rebuilt = revised_receipt(event, counts)
                    if any(receipt.get(key) != rebuilt.get(key)
                           for key in ("verification", "place_verified")):
                        counts["placement_receipt_status_mismatch"] += 1
                        diffs.append({**location, "kind": "placement_receipt_status_mismatch",
                                      "recorded": receipt, "recomputed": rebuilt,
                                      "measurements": event.get("verification_measurements")})
            if sha(Path(descriptor["path"])) != descriptor["sha256"]:
                raise ValueError("Trace changed during audit")
        report["groups"].append({"name": group["name"], "scope": group["scope"],
                                 "counts": dict(counts), "differences": diffs, "traces": traces})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.index.read_text()))
    report.update(index_sha256=sha(args.index), script_sha256=sha(Path(__file__)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"groups": [{"name": g["name"], "counts": g["counts"]}
                                 for g in report["groups"]], "report_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
