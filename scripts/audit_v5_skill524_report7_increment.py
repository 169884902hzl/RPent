"""Audit only the appended closed-prefix rows after immutable report6.

The upstream prefix auditor has already checked each current choices file. This
report keeps report6's records as a referenced immutable object and writes only
the 36 newly closed rows, while retaining cumulative arm/rep0/Wilson summaries.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes: int, known: int) -> list[float] | None:
    if not known:
        return None
    z = 1.959963984540054
    p = successes / known
    d = 1 + z * z / known
    centre = (p + z * z / (2 * known)) / d
    half = z * ((p * (1 - p) / known + z * z / (4 * known * known)) ** .5) / d
    return [max(0., centre - half), min(1., centre + half)]


def counts(rows: list[dict], key: str) -> dict:
    success = sum(row[key] is True for row in rows)
    failure = sum(row[key] is False for row in rows)
    known = success + failure
    return {"rows": len(rows), "successes": success, "failures": failure,
            "unknown": len(rows) - known, "known_denominator": known,
            "known_success_rate": success / known if known else None,
            "wilson95_known": wilson(success, known)}


def cumulative_metrics(arms: list[dict]) -> list[dict]:
    # Copy exactly the upstream cumulative summaries, including rep0 selection,
    # Wilson denominator and unknown accounting. No old row is reclassified.
    return json.loads(json.dumps(arms))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-report", type=Path, required=True)
    parser.add_argument("--current-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old_bytes, current_bytes = args.old_report.read_bytes(), args.current_report.read_bytes()
    old, current = json.loads(old_bytes), json.loads(current_bytes)
    old_rows = {row["case"]: row for row in old["records"]}
    current_rows = {row["case"]: row for row in current["records"]}
    if len(old_rows) != old["recorded"] or len(current_rows) != current["recorded"]:
        raise ValueError("duplicate or inconsistent report records")
    common = set(old_rows).intersection(current_rows)
    if common != set(old_rows):
        raise ValueError("report7 does not retain every report6 case")
    if any(old_rows[name] != current_rows[name] for name in common):
        raise ValueError("a report6 record changed")
    if any(old_rows[name]["choices_sha256"] != current_rows[name]["choices_sha256"] for name in common):
        raise ValueError("a report6 choices SHA changed")
    delta = [current_rows[name] for name in current_rows if name not in old_rows]
    if len(delta) != current["recorded"] - old["recorded"] or not delta:
        raise ValueError("no actual append-only increment")
    if current.get("choices_sha_mismatches") != 0 or current.get("choices_sha_checked") != current["recorded"]:
        raise ValueError("upstream choices SHA audit is incomplete")
    if old.get("choices_sha_mismatches") != 0 or old.get("choices_sha_checked") != old["recorded"]:
        raise ValueError("report6 choices SHA audit was incomplete")
    delta_groups = {}
    for row in delta:
        delta_groups.setdefault((row["class"], row["condition"]), []).append(row)
    moka_handle_outcomes = []
    for row in delta:
        if row["class"] != "moka pot" or row["condition"] != "handle_full_subtask160":
            continue
        if row["actual_actions"] <= 0 or row["chunks"] <= 0:
            execution_status = "not_executed_or_no_handle_call"
        else:
            execution_status = "executed"
        if row["failure"] == "private_measurement_unknown":
            measurement_status = "handle_or_physical_measurement_missing"
        elif row["failure"] == "no_sustained_grasp_during_subtask":
            measurement_status = "known_no_sustained_grasp"
        elif row["failure"] == "sustained_grasp_then_released_target_not_satisfied":
            measurement_status = "known_sustained_grasp_target_false"
        else:
            measurement_status = "known_target_result"
        moka_handle_outcomes.append({
            "case": row["case"], "seed": row["episode"]["seed"],
            "execution_status": execution_status,
            "measurement_status": measurement_status,
            "sustained_during": row["sustained_during"],
            "sustained_at_end": row["sustained_at_end"],
            "target_truth": row["target_truth"],
            "public_place_verified": row["public_place_verified"],
            "actual_actions": row["actual_actions"], "chunks": row["chunks"],
            "stop": row["receipt_stop"], "choices_sha256": row["choices_sha256"],
        })
    result = {
        "scope": "3670 append-only closed-prefix report7; report6 immutable",
        "job": current["job"],
        "previous_report": {"path": str(args.old_report), "sha256": sha(args.old_report),
                             "recorded": old["recorded"]},
        "current_upstream_report": {"path": str(args.current_report), "sha256": sha(args.current_report),
                                    "recorded": current["recorded"], "planned": current["planned"]},
        "append_only": True, "previous_records_unchanged": True,
        "previous_choices_sha_unchanged": True,
        "delta_rows": len(delta), "cumulative_rows": current["recorded"],
        "cumulative_planned": current["planned"],
        "upstream_choices_sha_checked": current["choices_sha_checked"],
        "upstream_choices_sha_mismatches": current["choices_sha_mismatches"],
        "delta_groups": {
            f"{group}/{condition}": {
                "rows": len(rows),
                "sustained_during": dict(Counter(str(row["sustained_during"]) for row in rows)),
                "sustained_at_end": dict(Counter(str(row["sustained_at_end"]) for row in rows)),
                "target_truth": dict(Counter(str(row["target_truth"]) for row in rows)),
                "failure_counts": dict(Counter(row["failure"] for row in rows)),
                "seeds": [row["episode"]["seed"] for row in rows],
                "records": rows,
            }
            for (group, condition), rows in sorted(delta_groups.items())
        },
        "moka_handle_delta_outcomes": moka_handle_outcomes,
        "cumulative_arms": cumulative_metrics(current["arms"]),
        "records": delta,
        "old_truth_definition": "3670 report6 source/private_grasp_phase; v2 is not substituted",
        "v2_status": "new code only; not applied to 3670 labels",
        "unknown_policy": "unknown remains separate and excluded from known Wilson denominators",
        "qualification_authorized": False,
        "new_training_rows": 0,
        "new_physics_trials": 0,
        "limits": [
            "Cumulative nominal rows repeat original scenes and are descriptive only.",
            "Rep0 is the first explicit initial_state_repetition=0 row per suite/task/seed, with no outcome selection.",
            "Handle/moka rows are exploratory complete-subtask evidence, not an independent first-grasp confirmation batch.",
            "Missing handle rows are not labeled failures; only closed newline-delimited rows are counted.",
            "The new grasp-truth v2 source is not used to rewrite this 3670 report.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "report.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# 3670 report7 append-only intermediate statistics", "",
             f"Report6 retained unchanged ({old['recorded']} rows); report7 adds {len(delta)} closed rows for cumulative {current['recorded']}/{current['planned']}.",
             "", "| New arm | rows | sustained during | sustained at end | target truth | failure counts |", "|---|---:|---|---|---|---|"]
    for key, group in result["delta_groups"].items():
        lines.append(f"| {key} | {group['rows']} | {group['sustained_during']} | {group['sustained_at_end']} | {group['target_truth']} | {group['failure_counts']} |")
    lines += ["", "## New rows", ""]
    for row in delta:
        lines.append(f"- `{row['case']}`: during={row['sustained_during']}, target={row['target_truth']}, failure={row['failure']}; choices SHA `{row['choices_sha256']}`")
    lines += ["", "## New moka-handle rows", "",
              "The three newly closed handle rows all executed 160 chunks; no not-executed or handle-measurement-missing row is silently counted as a physical failure. Two have known no-sustained-grasp evidence; one has known sustained grasp during transfer but false target predicate. Public placement unknown remains unknown.", "",
              "| Seed | Execution | Physical grasp evidence | Target truth | Public place | Actions/chunks |", "|---:|---|---|---|---|---:|"]
    for row in moka_handle_outcomes:
        lines.append(f"| {row['seed']} | {row['execution_status']} | {row['measurement_status']} | {row['target_truth']} | {row['public_place_verified']} | {row['actual_actions']}/{row['chunks']} |")
    lines += ["", "## Cumulative unchanged accounting", "",
              f"The upstream current prefix auditor checked {current['choices_sha_checked']} choices files with {current['choices_sha_mismatches']} mismatches. Report6's {old['recorded']} choices and all row fields match byte-for-byte at the JSON value level. Cumulative arm summaries, including independent repetition-0 selection, Wilson intervals and unknown denominators, are copied from the upstream report7 auditor output.",
              "", "The old 3670 private truth definition remains active for this report. The new v2 support rule is code-only and does not relabel report6 or report7.", "",
              f"Report SHA256: {sha(output)}"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"delta_rows": len(delta), "cumulative_rows": current["recorded"],
                      "report_sha256": sha(output)}))


if __name__ == "__main__":
    main()
