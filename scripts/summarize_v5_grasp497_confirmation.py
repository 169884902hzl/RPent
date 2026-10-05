"""Audit explicitly registered independent grasp-confirmation records on CPU."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from scripts.prepare_v5_grasp495_remaining_confirmation import make_official_state_validator
from scripts.summarize_v5_grasp449_20261005 import contact_executed, sha, truth_metrics, wilson


POOL_SHA = "89ea5ea7ee50e1cf7dc9eeafcdb925b299cc6cab541090e2b174bbad98fd8f64"
GROUPS = ("bottle", "bowl", "box", "mug", "frypan", "moka_pot")


def scene_key(case):
    episode = case["episode"]
    return episode["suite"], episode["task"], episode["seed"]


def metrics(rows, planned):
    result = truth_metrics(rows, planned)
    matrix = result["confusion"]
    result.update(
        success_over_planned=result["true_successes"] / planned if planned else None,
        unobserved_or_unknown_truth=planned - result["known_truth"],
        wilson_95CI=wilson(result["true_successes"], result["known_truth"]),
        false_positive_count=matrix.get("fp", 0),
        false_positive_denominator_true_failures=matrix.get("fp", 0) + matrix.get("tn", 0),
        false_negative_count=matrix.get("fn", 0),
        false_negative_denominator_true_successes=matrix.get("fn", 0) + matrix.get("tp", 0),
        contact_not_executed=len(rows) - sum(contact_executed(row) for row in rows),
    )
    return result


def summarize_confirmation(pool_path, manifest_paths, ledger_paths):
    """Preserve recorded truth; authorize a gate only after independent-state audit."""
    pool_path = Path(pool_path)
    if sha(pool_path) != POOL_SHA:
        raise ValueError("registered original confirmation pool changed")
    pool = json.loads(pool_path.read_text())
    prior_path = Path(pool["source_manifest"]["path"])
    if sha(prior_path) != pool["source_manifest"]["sha256"]:
        raise ValueError("registered discovery manifest changed")
    prior = json.loads(prior_path.read_text())
    old_tuples = {scene_key(case) for case in prior["cases"]}
    state_sha_for, verify_case_assets = make_official_state_validator(pool)
    old_hashes = {state_sha_for(*key) for key in sorted(old_tuples)}
    reserved = {(case["group"], *scene_key(case)): case for case in pool["cases"]}
    if len(reserved) != len(pool["cases"]):
        raise ValueError("confirmation pool repeats a class/state tuple")

    planned, manifests = {}, []
    for path in map(Path, manifest_paths):
        plan = json.loads(path.read_text())
        if (plan["pool_manifest"]["sha256"] != POOL_SHA
                or not plan.get("cohort", "").startswith("independent_confirmation_")):
            raise ValueError("only preregistered independent confirmation manifests are accepted")
        manifests.append({"path": str(path), "sha256": sha(path)})
        for case in plan["cases"]:
            name, group = case["name"], case["group"]
            registered = reserved.get((group, *scene_key(case)))
            if (name in planned or group not in GROUPS or registered is None
                    or any(case.get(key) != value for key, value in registered.items() if key != "name")
                    or group not in plan.get("frozen_class_recipes", {})
                    or case["condition"] not in plan["conditions"]):
                raise ValueError("unregistered, changed, or duplicated confirmation case")
            planned[name] = case

    tuple_classes, hash_classes = defaultdict(set), defaultdict(set)
    class_audits, verified_tasks = {}, set()
    for group in GROUPS:
        cases = [case for case in planned.values() if case["group"] == group]
        tuples = [scene_key(case) for case in cases]
        hashes = [case["state_sha256"] for case in cases]
        if len(set(tuples)) != len(tuples) or len(set(hashes)) != len(hashes):
            raise ValueError("confirmation repeats a scene tuple or raw state within a class")
        if set(tuples) & old_tuples or set(hashes) & old_hashes:
            raise ValueError("confirmation overlaps discovery tuple or raw state")
        for case in cases:
            key = scene_key(case)
            if key[:2] not in verified_tasks:
                verify_case_assets(case)
                verified_tasks.add(key[:2])
            if state_sha_for(*key) != case["state_sha256"]:
                raise ValueError("registered official confirmation state changed")
            tuple_classes[key].add(group)
            hash_classes[case["state_sha256"]].add(group)
        class_audits[group] = {"planned": len(cases), "unique_scene_tuples": len(set(tuples)),
                              "unique_raw_state_hashes": len(set(hashes)),
                              "discovery_tuple_overlap": 0, "discovery_raw_state_overlap": 0}

    rows, seen, ledgers, missing_ledgers, missing_choices = [], set(), [], [], []
    infrastructure = Counter()
    for path in map(Path, ledger_paths):
        if not path.is_file():
            missing_ledgers.append(str(path))
            continue
        ledgers.append({"path": str(path), "sha256": sha(path)})
        for line in path.read_text().splitlines():
            row = json.loads(line)
            case = row["case"]
            name = case["name"]
            if case != planned.get(name) or name in seen:
                raise ValueError("unregistered, changed, or duplicated physical confirmation trial")
            seen.add(name)
            choices = Path(row["output_dir"]) / "choices.jsonl"
            if not choices.is_file():
                missing_choices.append({"case": name, "path": str(choices)})
            elif sha(choices) != row.get("choices_sha256"):
                raise ValueError(f"recorded choices SHA changed: {name}")
            if row.get("raised_error"):
                infrastructure["raised_error"] += 1
            if row["first_receipt"].get("verification") == "execution_error":
                infrastructure["execution_error"] += 1
            if row.get("result", {}).get("status") in {"startup_error", "runtime_error", "error"}:
                infrastructure["startup_or_runtime_error"] += 1
            rows.append(row)

    by_class = {group: metrics([row for row in rows if row["case"]["group"] == group],
                               class_audits[group]["planned"]) for group in GROUPS}
    overall = metrics(rows, len(planned))
    reasons = []
    if any(audit["unique_scene_tuples"] < 100 or audit["unique_raw_state_hashes"] < 100
           for audit in class_audits.values()):
        reasons.append("fewer_than_100_registered_independent_states_in_each_of_six_classes")
    if seen != planned.keys() or missing_ledgers:
        reasons.append("missing_physical_trials_or_explicit_ledgers")
    if missing_choices:
        reasons.append("missing_recorded_choices_evidence")
    if overall["known_truth"] != len(planned):
        reasons.append("unknown_truth_not_scored_as_model_failure")
    if infrastructure:
        reasons.append("infrastructure_or_execution_error")
    if any(value["contact_executed"] != value["planned"] or value["contact_executed"] < 100
           for value in by_class.values()):
        reasons.append("insufficient_executed_contact_trials")
    authorized = not reasons
    numeric_reasons = []
    if overall["success_over_planned"] is None or overall["success_over_planned"] < .95:
        numeric_reasons.append("overall_confirmed_success_below_95_percent_of_planned_trials")
    if any(value["success_over_planned"] is None or value["success_over_planned"] < .9
           for value in by_class.values()):
        numeric_reasons.append("class_confirmed_success_below_90_percent_of_planned_trials")
    if overall["verifier_agreement"] is None or overall["verifier_agreement"] < .95:
        numeric_reasons.append("verifier_agreement_below_95_percent")
    return {
        "scope": "independent original-task first-grasp confirmation only; no exploration merging, behavior freeze, or training admission",
        "pool": {"path": str(pool_path), "sha256": POOL_SHA},
        "discovery_manifest": pool["source_manifest"], "manifests": manifests, "ledgers": ledgers,
        "script_sha256": sha(__file__), "python": sys.executable,
        "state_validation": "official original LIBERO CPU decoding through the pinned config; no simulation rollout",
        "prior_unique_scene_tuples": len(old_tuples), "prior_unique_raw_state_hashes": len(old_hashes),
        "class_state_audits": class_audits,
        "cross_class_shared_scene_tuples": sum(len(groups) > 1 for groups in tuple_classes.values()),
        "cross_class_shared_raw_state_hashes": sum(len(groups) > 1 for groups in hash_classes.values()),
        "cross_class_raw_state_reuse": [{"state_sha256": digest, "classes": sorted(groups)}
                                       for digest, groups in sorted(hash_classes.items()) if len(groups) > 1],
        "ci_scope": "Wilson nominal binomial intervals over known recorded truth only; 100 distinct states are audited within each class. Cross-class scene/state reuse is disclosed and pooled independence is not assumed.",
        "qualification_denominator": "all preregistered trials, including missing/unknown/nonexecuted trials; these are never credited as successes or silently replaced",
        "truth_labels_recomputed": False, "overall": overall, "by_class": by_class,
        "missing_cases": sorted(planned.keys() - seen), "missing_ledgers": missing_ledgers,
        "missing_choices": missing_choices, "infrastructure_counts": dict(infrastructure),
        "complete": seen == planned.keys() and not missing_ledgers,
        "qualification_authorized": authorized,
        "qualification_passed": authorized and not numeric_reasons,
        "qualification_reasons": reasons + numeric_reasons,
        "new_training_rows": 0, "new_physical_trials": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize_confirmation(args.pool, args.manifest, args.ledger)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "recorded": report["overall"]["recorded"],
                      "qualification_passed": report["qualification_passed"], "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
