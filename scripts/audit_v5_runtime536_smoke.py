"""Audit only the twenty manifest-declared physical smoke episode outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.manifest.read_text())
    cases = []
    for file in index["files"]:
        path = Path(file["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != file["sha256"]:
            raise ValueError(f"changed explicit manifest: {path}")
        plan = json.loads(path.read_text())
        for episode in plan["episodes"]:
            out = args.job_root / f"part{file['part']}" / file["cohort"] / (
                f"{episode['suite']}_t{episode['task']}_s{episode['seed']}")
            choices = lines(out / "choices.jsonl")
            history = lines(out / "measurement_history.jsonl")
            result = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else {}
            fusion, cameras = Counter(), Counter()
            for row in choices:
                for value in row.get("perception_measurement_evidence", {}).values():
                    fusion[value.get("fusion_version", "unmeasured")] += 1
                    cameras.update(value.get("source_cameras", []))
            max_repeat, run, previous = 0, 0, None
            no_effect = 0
            blocked_seen = set()
            blocked_selected = []
            subtask_candidates = subtask_selected = subtask_verified = subtask_unmeasured = 0
            measured_receipts = 0
            action_attempts = Counter()
            failed_action_attempts = Counter()
            for row in choices:
                action = row["selected"]
                action_attempts[action] += 1
                run = run + 1 if action == previous else 1
                max_repeat = max(max_repeat, run)
                previous = action
                receipt = row.get("receipt", {})
                if (receipt.get("effect") == "no_effect"
                        or receipt.get("verification") in ("failed", "execution_error")):
                    failed_action_attempts[action] += 1
                no_effect += receipt.get("effect") == "no_effect"
                measured_receipts += (receipt.get("receipt_version") == "measured_action/1"
                                     and "gripper_m" in receipt.get("measurement", {})
                                     and "held" in receipt.get("measurement", {}))
                context = row["request"]["context"]
                blocked = [line[len("blocked "):].split(" failures=", 1)[0]
                           for line in context.splitlines() if line.startswith("blocked ")]
                blocked_seen.update(blocked)
                if action in blocked:
                    blocked_selected.append(row["decision"])
                subtask_candidates += any(c.startswith("vla_subtask(") for c in row["candidates"])
                if action.startswith("vla_subtask("):
                    subtask_selected += 1
                    subtask_verified += receipt.get("verification") == "verified"
                    subtask_unmeasured += receipt.get("verification") == "unmeasured"
            defects = []
            if result.get("status") in ("error", "startup_error"):
                defects.append(result.get("error", "runtime error"))
            if choices and measured_receipts != len(choices):
                defects.append("missing measured receipt changes")
            if max_repeat > 5:
                defects.append("identical action consecutive repeat exceeds five")
            if blocked_selected:
                defects.append("selected an action recorded as blocked")
            if choices and not subtask_candidates:
                defects.append("vla_subtask absent for entire episode")
            # Report entity-level evidence separately from the refresh toggle:
            # cached/unmeasured parts never inflate the fusion success count.
            measured = fusion["rgbd_dual_view/1"] + fusion["none"]
            if measured and fusion["rgbd_dual_view/1"] / measured <= .5:
                defects.append("dual view not majority of measured entity evidence")
            cases.append({"episode": episode, "cohort": file["cohort"], "output": str(out),
                          "complete": bool(result), "decisions_recorded": len(choices),
                          "official_success": result.get("official_success"),
                          "termination": result.get("termination_category"),
                          "fusion_versions": dict(fusion), "source_cameras": dict(cameras),
                          "refresh_fusion_versions": dict(Counter(h.get("fusion_version") for h in history)),
                          "no_effect": no_effect, "blocked_actions": sorted(blocked_seen),
                          "maximum_consecutive_identical_action": max_repeat,
                          "maximum_total_identical_action_attempts": max(action_attempts.values(), default=0),
                          "action_attempts": dict(action_attempts),
                          "failed_action_attempts": dict(failed_action_attempts),
                          "subtask_available_steps": subtask_candidates, "subtask_selected": subtask_selected,
                          "subtask_verified": subtask_verified, "subtask_unmeasured": subtask_unmeasured,
                          "measured_receipts": measured_receipts, "defects": defects,
                          "wall_s": result.get("wall_s")})
    report = {"planned": index["total"], "completed": sum(c["complete"] for c in cases),
              "official_success": sum(c["official_success"] is True for c in cases),
              "defects": sum(bool(c["defects"]) for c in cases), "cases": cases,
              "passed": all(c["complete"] and c["decisions_recorded"] and not c["defects"] for c in cases)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("planned", "completed", "official_success", "defects", "passed")}))


if __name__ == "__main__":
    main()
