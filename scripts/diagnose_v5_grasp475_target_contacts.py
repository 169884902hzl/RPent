"""Separate unlifted targets from other-object contact in explicit saved trials.

Other-object body-origin rise with opposing-pad contact is a diagnostic proxy,
not a collision-clearance/sustained-hold truth label. Original labels stay intact.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_contacts(row):
    initial = row["initial_private_reference"]["objects"]
    selected = row["final_private_contact"]["selected_symbol"]
    other_samples = []
    target_samples = 0
    for index, sample in enumerate(row["contact_samples"]):
        target_samples += sample["objects"][selected]["dual_finger_contact"]
        for name, body in sample["objects"].items():
            if name == selected:
                continue
            rise = body["xyz"][2] - initial[name]["xyz"][2]
            if body["dual_finger_contact"] and rise >= .03:
                other_samples.append({"chunk": index, "sim_time": sample["sim_time"],
                                      "name": name, "body_origin_rise_m": rise})
    return {"case": row["case"], "truth": row.get("true_sustained_grasp"),
            "selected_private_symbol": selected, "target_dual_contact_samples": target_samples,
            "other_contact_and_rise_proxy": bool(other_samples),
            "other_contact_samples": other_samples,
            "public_pick_success": (row.get("rpent_pick_result") or {}).get("success"),
            "prompt": row.get("contact_prompt"), "chunks": row["chunks"],
            "max_chunks": row.get("contact_max_chunks"), "original_receipt": row["first_receipt"],
            "output_dir": row["output_dir"], "choices_sha256": row["choices_sha256"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows, sources, seen = [], [], set()
    for ledger in args.ledger:
        raw = ledger.read_bytes()
        # Only closed immutable ledgers (or explicitly captured prefixes) are
        # inputs. Never consume an unfinished JSON line from a live writer.
        if not raw.endswith(b"\n"):
            raise ValueError("ledger ends with an incomplete record")
        sources.append({"path": str(ledger), "sha256": hashlib.sha256(raw).hexdigest()})
        for line in raw.splitlines():
            trial = json.loads(line)
            path = Path(trial["output_dir"]) / "choices.jsonl"
            if path in seen or sha(path) != trial["choices_sha256"]:
                raise ValueError("duplicate or changed saved physical trace")
            seen.add(path)
            rows.append({**target_contacts(trial), "cohort": ledger.parent.name})
    groups = defaultdict(Counter)
    for row in rows:
        counts = groups[(row["cohort"], row["case"]["group"], row["case"]["condition"])]
        counts["trials"] += 1
        counts["true" if row["truth"] is True else "false" if row["truth"] is False else "unknown"] += 1
        if row["truth"] is False:
            counts["false_with_other_contact_and_rise_proxy"] += row["other_contact_and_rise_proxy"]
            counts["false_without_any_target_dual_contact"] += row["target_dual_contact_samples"] == 0
            counts["false_at_chunk_budget"] += row["chunks"] == row["max_chunks"]
    report = {"scope": "CPU saved-contact diagnosis; no changed labels or new physics",
              "rows": rows, "sources": sources, "script_sha256": sha(__file__),
              "by_cohort_class_condition": [{"cohort": cohort, "class": group,
                  "condition": condition, **dict(counts)}
                  for (cohort, group, condition), counts in sorted(groups.items())],
              "private_labels_enter_runtime": False, "new_training_rows": 0,
              "limits": ["Opposing-pad contact can miss legitimate single-finger rim/handle support.",
                         "Other-object body-origin rise does not establish whole-geometry clearance or0.5s hold.",
                         "Proxy only diagnoses low-level execution; it is not a decider wrong-object score.",
                         "Do not infer a full condition score from a captured partial prefix."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"recorded": len(rows), "by_cohort_class_condition": report["by_cohort_class_condition"],
                      "report_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
