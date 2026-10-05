"""Summarize explicit paired first-grasp records, retaining incomplete trials."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import math


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    scale = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / scale
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / scale
    return [centre - radius, centre + radius]


def truth_metrics(rows, planned):
    matrix, failures = Counter(), Counter()
    known, successful = 0, 0
    for row in rows:
        truth = row.get("true_sustained_grasp")
        visual = row["visual_verified"]
        if not isinstance(truth, bool):
            matrix["unknown_truth"] += 1
            failures["private_truth_unavailable"] += 1
            continue
        known += 1
        successful += truth
        matrix["tp" if truth and visual else "fn" if truth else "fp" if visual else "tn"] += 1
        if not truth:
            receipt = row["first_receipt"]
            if receipt.get("verification") == "execution_error":
                failures["execution_error"] += 1
            elif receipt.get("stop") in ("approach_not_reached", "waypoint_not_reached", "wrist_pose_not_reached"):
                failures[receipt["stop"]] += 1
            else:
                checks = row.get("sustained_hold", {}).get("truth", {}).get("checks", [])
                if any(c["clearance_m"] >= .03 and c["finger_contact"] for c in checks):
                    failures["hold_not_sustained"] += 1
                elif any(c["clearance_m"] >= .03 for c in checks):
                    failures["lift_without_finger_support"] += 1
                elif any(c["finger_contact"] for c in checks):
                    failures["finger_contact_without_support_clearance"] += 1
                else:
                    failures["no_target_lift_or_hold"] += 1
        if truth and not visual:
            failures["visual_false_negative"] += 1
        elif visual and not truth:
            failures["visual_false_positive"] += 1
    agreement = (matrix["tp"] + matrix["tn"]) / known if known else None
    negatives, positives = matrix["fp"] + matrix["tn"], matrix["tp"] + matrix["fn"]
    unique = {(r["case"]["episode"]["suite"], r["case"]["episode"]["task"],
               r["case"]["episode"]["seed"]) for r in rows}
    return {"planned": planned, "recorded": len(rows), "known_truth": known,
            "first_grasp_attempts": sum(r["grasp_attempted"] for r in rows),
            "true_successes": successful, "true_success_rate": successful / known if known else None,
            "wilson_95CI": wilson(successful, known), "confusion": dict(matrix),
            "verifier_agreement": agreement,
            "false_positive_rate": matrix["fp"] / negatives if negatives else None,
            "false_negative_rate": matrix["fn"] / positives if positives else None,
            "failure_counts": dict(failures), "unique_original_initial_states": len(unique),
            "wilson_scope": "nominal binomial trial interval; repeated initial-state count disclosed",
            "complete_truth_protocol": len(rows) == planned == known}


def supported_hold(sample):
    """Separate opposing pads from a lifted handle/rim supported by one finger.

    This is a private diagnostic definition, not a runtime stop condition.
    Unknown binding remains unknown. Raw contacts and both definitions stay
    available; a single pad test is not ground truth for every object shape.
    """
    name = sample.get("selected_symbol")
    rise = sample.get("private_z_rise_m")
    if name is None or rise is None:
        return None
    def touching_object(geom):
        return geom is not None and geom.startswith(name + "_")
    def touching_finger(geom):
        return geom is not None and geom.startswith("gripper") and "finger" in geom
    contact = any((touching_object(c["geom1"]) and touching_finger(c["geom2"]))
                  or (touching_object(c["geom2"]) and touching_finger(c["geom1"]))
                  for c in sample.get("contacts", []))
    return bool(rise >= .03 and (contact or sample.get("target_dual_contact")))


def summarize(rows, planned):
    counts, dual_matrix, held_matrix = Counter(), Counter(), Counter()
    for row in rows:
        counts["grasp_attempted"] += row["grasp_attempted"]
        counts["visual_verified"] += row["visual_verified"]
        counts["execution_error"] += row["first_receipt"].get("verification") == "execution_error"
        counts["runtime_exception"] += bool(row.get("raised_error"))
        sample = row.get("final_private_contact") or {}
        dual, hold = sample.get("target_dual_contact"), supported_hold(sample)
        for value, matrix in ((dual, dual_matrix), (hold, held_matrix)):
            if value is None:
                matrix["unknown"] += 1
            else:
                predicted = row["visual_verified"]
                matrix["tp" if predicted and value else "fp" if predicted else "fn" if value else "tn"] += 1
        counts["dual_contact"] += dual is True
        counts["contact_supported_lift"] += hold is True
        counts["not_yet_run"] = planned - len(rows)
    return {"planned": planned, "recorded": len(rows), "complete": len(rows) == planned,
            "counts": dict(counts),
            "visual_success_over_all_planned": counts["visual_verified"] / planned,
            "contact_supported_lift_over_all_planned": counts["contact_supported_lift"] / planned,
            "dual_contact_confusion": dict(dual_matrix), "contact_supported_lift_confusion": dict(held_matrix),
            "wall_median_s": statistics.median(r["wall_s"] for r in rows) if rows else None,
            "chunks_median": statistics.median(r["chunks"] for r in rows) if rows else None,
            "executed_vla_actions": sum(r["executed_vla_actions"] for r in rows),
            "at_least_50_first_attempts": counts["grasp_attempted"] >= 50}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    planned = {case["name"]:case for case in plan["cases"]}
    seen, rows, sources = set(), [], []
    for ledger in args.ledger:
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for row in map(json.loads, ledger.read_text().splitlines()):
            case = row["case"]
            if case != planned.get(case["name"]) or case["name"] in seen:
                raise ValueError("unregistered or duplicated trial")
            seen.add(case["name"])
            rows.append(row)
    by_group = {}
    for condition in plan["conditions"]:
        for group in plan["groups"]:
            members = [r for r in rows if r["case"]["condition"] == condition and r["case"]["group"] == group]
            expected = sum(c["condition"] == condition and c["group"] == group for c in planned.values())
            by_group[f"{condition}/{group}"] = summarize(members, expected)
    pairs = defaultdict(list)
    for row in rows:
        c = row["case"]
        pairs[(c["group"], c["episode"]["suite"], c["episode"]["task"], c["episode"]["seed"])].append(row)
    mismatches = []
    for key, trials in pairs.items():
        if len(trials) < 2:
            continue
        ref = trials[0].get("initial_private_reference", {}).get("objects", {})
        for row in trials[1:]:
            other = row.get("initial_private_reference", {}).get("objects", {})
            if ref.keys() != other.keys():
                mismatches.append({"pair": key, "case": row["case"]["name"], "reason": "object_reference_set_changed"})
                continue
            difference = max((sum((ref[n]["xyz"][i] - other[n]["xyz"][i]) ** 2 for i in range(3)) ** .5
                              for n in ref), default=0.)
            if difference > .001:
                mismatches.append({"pair": key, "case": row["case"]["name"], "max_initial_object_delta_m": difference})
    report = {"scope": "original-task paired component diagnosis; no model task score or training admission",
              "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__),
              "sources": sources, "recorded": len(rows), "planned": len(planned),
              "complete": seen == planned.keys(), "by_condition_group": by_group,
              "initial_reference_mismatches_over_1mm": mismatches,
              "private_hold_definition": "3cm body rise with target-finger contact; dual-pad predicate separately retained",
              "runtime_grasp_verifier_changed": False, "new_training_rows": 0}
    if plan.get("truth_protocol"):
        methods = {}
        for condition in plan["conditions"]:
            group_metrics = {group: truth_metrics(
                [r for r in rows if r["case"]["condition"] == condition and r["case"]["group"] == group],
                sum(c["condition"] == condition and c["group"] == group for c in planned.values()))
                for group in plan["groups"]}
            method = truth_metrics([r for r in rows if r["case"]["condition"] == condition],
                                   sum(c["condition"] == condition for c in planned.values()))
            method["by_class"] = group_metrics
            method["meets_user_grasp_gate"] = bool(method["complete_truth_protocol"] and
                all(g["first_grasp_attempts"] >= 100 and g["true_success_rate"] >= .9
                    for g in group_metrics.values()) and method["true_success_rate"] >= .95
                and method["verifier_agreement"] >= .95)
            methods[condition] = method
        report["truth_protocol"] = plan["truth_protocol"]
        report["sustained_truth_methods"] = methods
        report["qualifying_conditions"] = [k for k, v in methods.items() if v["meets_user_grasp_gate"]]
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "recorded": len(rows),
                      "planned": len(planned), "initial_mismatches": len(mismatches),
                      "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
