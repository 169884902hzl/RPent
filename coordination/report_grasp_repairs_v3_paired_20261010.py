"""Compare locked-v3 replays on identical registered selection-state bytes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from coordination.summarize_registered_grasp_v3r9 import metric, confusion


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_rows(parent):
    return [json.loads(line) for line in (parent / "rows.jsonl").open()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = {row["baseline_case"]: row for row in read_rows(args.before)}
    if len(before) != len(read_rows(args.before)):
        raise ValueError("before must contain one locked-v3 trial per state")
    rows, groups = [], defaultdict(list)
    for parent in args.after:
        for row in read_rows(parent):
            old = before[row["baseline_case"]]
            if old["state_sha256"] != row["state_sha256"]:
                raise ValueError("paired registered initial-state bytes differ")
            a, b = old["registered_v3"], row["registered_v3"]
            transition = ("unknown_in_pair" if a is None or b is None else
                          "improved" if a is False and b is True else
                          "regressed" if a is True and b is False else
                          "both_success" if a is True else "both_failure")
            item = {**row, "before_v3": a, "before_public": old["public"],
                    "before_failure_reason": old["failure_reason"],
                    "v3_transition": transition,
                    "before_physical_input": {"path": old["input"],
                        "sha256": old["input_sha256"], "line": old["line"]}}
            rows.append(item)
            groups[row["group"]].append(item)
    summaries = {}
    for group, items in groups.items():
        if len({row["baseline_case"] for row in items}) != len(items):
            raise ValueError("duplicate physical trial in one comparison group")
        summaries[group] = {
            "recorded_n": len(items),
            "before_v3": metric(sum(row["before_v3"] is True for row in items), len(items)),
            "after_v3": metric(sum(row["registered_v3"] is True for row in items), len(items)),
            "before_v3_unknown": sum(row["before_v3"] is None for row in items),
            "after_v3_unknown": sum(row["registered_v3"] is None for row in items),
            "transitions": dict(Counter(row["v3_transition"] for row in items)),
            "public_verifier_all_registered": confusion(items, "registered_v3"),
            "before_failure_reasons": dict(Counter(row["before_failure_reason"] for row in items)),
            "after_failure_reasons": dict(Counter(row["failure_reason"] for row in items)),
            "regressions": [{"case": row["case"], "baseline_case": row["baseline_case"],
                "reason": row["failure_reason"], "plan": row["new_plan"],
                "physical_input": {"path": row["input"], "sha256": row["input_sha256"],
                                   "line": row["line"]}}
                for row in items if row["v3_transition"] == "regressed"],
        }
    args.output.mkdir(parents=True, exist_ok=False)
    records = args.output / "rows.jsonl"
    records.write_text("".join(json.dumps(row) + "\n" for row in rows))
    report = {"before": pin(args.before / "rows.jsonl"),
        "after": [pin(parent / "rows.jsonl") for parent in args.after],
        "producer": pin(Path(__file__)), "records": pin(records), "groups": summaries,
        "registered_v3_source_sha256": "d8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f",
        "limits": ["Before is a fresh same-state servo-only replay, not the original r14 exclusive-v2 label.",
                   "Unknown truth and missing public verdict remain in registered denominators.",
                   "Selection results are not independent confirmation or training admission."],
        "training_allowed": False, "qualification_allowed": False}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({group: {key: value for key, value in summary.items()
                            if key != "regressions"} for group, summary in summaries.items()}))


if __name__ == "__main__":
    main()
