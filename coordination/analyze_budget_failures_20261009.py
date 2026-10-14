"""Preserve failed-episode step costs and observed motion classifications."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from robots.libero.v5_motion_classification import classify_move


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    failures, motions, inputs = [], [], [ref(args.episodes), ref(Path(__file__))]
    for row in rows(args.episodes):
        if row["result"].get("official_success"):
            continue
        choice_ref = row["trace"].get("choices")
        if not choice_ref:
            continue
        path = Path(choice_ref["path"])
        if ref(path) != choice_ref:
            raise ValueError("recorded choices changed after cohort summary")
        inputs.append(choice_ref)
        events = rows(path)
        receipts = Counter()
        actions = Counter()
        costs = Counter()
        attempts = []
        for event in events:
            receipt = event.get("receipt") or {}
            tool = receipt.get("tool") or event["selected"].partition("(")[0]
            cause = receipt.get("failure_reason") or receipt.get("verification", "missing")
            receipts[f"{tool}/{cause}"] += 1
            actions[event["selected"]] += 1
            costs[tool] += receipt.get("sim_steps_used", 0)
            attempts.append({"decision": event["decision"], "selected": event["selected"],
                             "verification": receipt.get("verification"),
                             "failure_reason": receipt.get("failure_reason"),
                             "sim_steps": receipt.get("sim_steps_used"),
                             "remaining_sim_steps": receipt.get("remaining_sim_steps"),
                             "chunks": receipt.get("chunks"),
                             "approach_residual_m": receipt.get("approach_residual_m")})
            for move in event.get("motion_evidence", []):
                if move.get("name") != "move_to" or move.get("final_dist_m", 0) <= .02:
                    continue
                classified = (classify_move(move, event)
                              if move.get("last_10_steps") and move.get("final_contact_and_joints") is not None
                              else {"classification": "insufficient_motion_trace",
                                    "decision": event["decision"], "selected": event["selected"],
                                    "final_dist_m": move["final_dist_m"],
                                    "target_xyz": move.get("target_xyz"),
                                    "final_eef_pos": move.get("final_eef_pos"),
                                    "steps_used": move.get("steps_used")})
                motions.append({"episode": row["episode"], **classified,
                                "receipt_failure_reason": receipt.get("failure_reason"),
                                "receipt_verification": receipt.get("verification")})
        failures.append({"episode": row["episode"], "choices": choice_ref,
                         "budget_end_kind": row["result"].get("budget_end_kind"),
                         "execution_budget": row["result"].get("execution_budget"),
                         "decision_count": len(events), "skill_step_consumption": dict(costs),
                         "receipt_counts": dict(receipts), "action_counts": dict(actions),
                         "attempts": attempts})
    args.output.mkdir(parents=True, exist_ok=False)
    outputs = []
    for name, records in (("failures", failures), ("motion", motions)):
        path = args.output / f"{name}.jsonl"
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        outputs.append(ref(path))
    counts = Counter(row["classification"] for row in motions)
    report = {"episodes": len(failures), "motion_residual_over2cm": len(motions),
              "observed_motion_classes": dict(counts), "inputs": inputs, "outputs": outputs,
              "limitations": ["Residual over2cm includes accepted 2-to-8cm approach points.",
                              "Contact/joint observations do not establish causality or IK infeasibility.",
                              "No policy-memory-versus-script cause is inferred without paired execution."],
              "private_diagnostic_only": True, "training_allowed": False}
    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest), "failures": [
        {k: row[k] for k in ("episode", "decision_count", "skill_step_consumption", "receipt_counts")}
        for row in failures], "observed_motion_classes": dict(counts)}))


if __name__ == "__main__":
    main()
