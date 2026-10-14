"""Export execution-before scores with explicit public versus private labels."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.summarize_v5_online_success import executed_prediction


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [ref(args.episodes), ref(Path(__file__))]
    records, counts = [], Counter()
    for line in args.episodes.read_text().splitlines():
        episode = json.loads(line)
        choice = episode["trace"].get("choices")
        if choice is None:
            continue
        path = Path(choice["path"])
        if ref(path) != choice:
            raise ValueError("episode choices changed")
        inputs.append(choice)
        for line in path.read_text().splitlines():
            event = json.loads(line)
            measured, excluded = executed_prediction(event)
            diagnostic = event["answer"].get("pre_action_success_diagnostic")
            if diagnostic is None:
                counts["missing_pre_action_prediction"] += 1
                continue
            receipt = event.get("receipt") or {}
            counts["predictions_before_execution"] += 1
            score = diagnostic["p_success"]
            # executed_prediction validates saved state/action/probability
            # even for outcomes whose physical check is unknown.
            label = measured["actual_success"] if measured else None
            kind = "public_measured_receipt" if measured else "unknown"
            rule = measured["judge"] if measured else excluded
            if receipt.get("tool") == "vla_task" and receipt.get("executed"):
                if isinstance(receipt.get("task_completed"), bool) and isinstance(receipt.get("native_terminated"), bool):
                    if receipt["task_completed"] != receipt["native_terminated"]:
                        raise ValueError("complete task receipt disagrees with native endpoint signal")
                    label = int(receipt["native_terminated"])
                    kind, rule = "native_environment_signal", "native_terminated_after_executed_full_task"
            counts[f"labels/{kind}"] += 1
            records.append({"episode": episode["episode"], "decision": event["decision"],
                            "selected": event["selected"], "tool": receipt.get("tool"),
                            "p_success": score, "actual_success": label,
                            "label_source": kind, "label_rule": rule,
                            "private_simulation_truth": None, "private_sidecar_available": False,
                            "context_sha256": diagnostic["context_sha256"],
                            "phase": diagnostic["phase"], "selection_changed": False,
                            "choices": choice, "sim_steps_used": receipt.get("sim_steps_used"),
                            "training_allowed": False})
    args.output.mkdir(parents=True, exist_ok=False)
    paired = args.output / "predictions_and_outcomes.jsonl"
    paired.write_text("".join(json.dumps(row) + "\n" for row in records))
    report = {"counts": dict(counts), "records": ref(paired), "inputs": inputs,
              "label_limit": "public receipt checks and native whole-task signals; no private grasp/place labels were recorded in these runs",
              "private_labels_not_inferred_from_episode_success": True, "new_model_calls": 0,
              "selection_behavior_changed": False, "training_allowed": False}
    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest), "counts": dict(counts)}))


if __name__ == "__main__":
    main()
