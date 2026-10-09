"""Classify the actual moves in pinned original-task prefix diagnostics."""

import argparse
from collections import Counter
import json
from pathlib import Path

from summarize_v5_interim80_once_20261008 import pinned, read_rows, ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    diagnostic = root / "results/harness_v5/motion_classification_20261008_r4"
    import importlib.util

    cases, moves, inputs, identities = [], [], [], set()
    for group in ("group0", "group1"):
        prep = diagnostic / "preparation" / group / "manifest.json"
        plan = json.loads(prep.read_text())
        inputs.append(ref(prep))
        classifier_ref = next(item for item in plan["source_files"]
                              if item["path"].endswith("/v5_motion_classification.py"))
        classifier_path = pinned(classifier_ref)
        inputs.append(classifier_ref)
        spec = importlib.util.spec_from_file_location("motion_classifier", classifier_path)
        classifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(classifier)
        expected = {case["name"] for case in plan["cases"]}
        actual = set()
        for stage in ("startup", "formal"):
            report_path = diagnostic / group / stage / "probe/report.json"
            report = json.loads(report_path.read_text())
            inputs.append(ref(report_path))
            for case in report["cases"]:
                name = case["case"]["name"]
                if name not in expected or name in identities:
                    raise ValueError("Unexpected or repeated diagnostic case: " + name)
                identities.add(name)
                actual.add(name)
                path = pinned(case["choices"])
                inputs.append(ref(path))
                events = read_rows(path)
                current_moves = []
                for event in events:
                    for move in event.get("motion_evidence", []):
                        if move.get("name") == "move_to":
                            current_moves.append({"case": name, **classifier.classify_move(move, event)})
                moves.extend(current_moves)
                cases.append({"name": name, "group": group, "stage": stage,
                    "diagnostic_outcome": case["diagnostic_outcome"],
                    "recorded_decisions": len(events),
                    "request_equal_count": case["request_equal_count"],
                    "expected_decisions": case["case"]["prefix_decisions"],
                    "raised_error": case["raised_error"], "moves": len(current_moves)})
        if actual != expected:
            raise ValueError("Incomplete diagnostic group: " + group)
    failed = [m for m in moves if m["classification"] != "reached"]
    report = {"scope": "original-task development replay; diagnostic truth only, no training",
        "cases": cases, "moves": moves, "move_count": len(moves),
        "failed_move_count": len(failed),
        "failed_move_classification_counts": dict(Counter(m["classification"] for m in failed)),
        "case_outcome_counts": dict(Counter(c["diagnostic_outcome"] for c in cases)),
        "requests_equal": sum(c["request_equal_count"] for c in cases),
        "recorded_decisions": sum(c["recorded_decisions"] for c in cases),
        "limitations": ["Fresh Pi05 execution can diverge from the original prefix.",
            "A contact or joint-limit observation does not prove causal blockage.",
            "No IK infeasibility or yaw causality is inferred from position residuals."],
        "confirmation": False, "training_allowed": False}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    manifest = {"generator": ref(__file__), "inputs": inputs, "outputs": [ref(path)],
                "training_allowed": False}
    m = args.output / "manifest.json"
    m.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("move_count", "failed_move_count",
        "failed_move_classification_counts", "case_outcome_counts", "requests_equal", "recorded_decisions")}))
    print(json.dumps(ref(m)))


if __name__ == "__main__":
    main()
