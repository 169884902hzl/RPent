"""Account for the registered 80 states without selecting among duplicate runs."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    path = Path(item["path"])
    if not path.is_absolute() or ref(path)["sha256"] != item["sha256"]:
        raise ValueError(f"Pinned input changed: {path}")
    return path


def key(episode):
    return episode["suite"], int(episode["task"]), int(episode["seed"])


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def classify(result):
    if result.get("official_success") is True:
        return "functional", "success"
    error = str(result.get("error", ""))
    if "Object of type bool_ is not JSON serializable" in error:
        return "infrastructure", "bool_serialization"
    category = result.get("termination_category") or "unclassified"
    # The registered prompt admission rule is a functional failure, not an
    # infrastructure retry opportunity, even if old bookkeeping flags disagree.
    if category == "over_token":
        return "functional", "over_token"
    if result.get("infrastructure_failure") or category == "startup_error":
        return "infrastructure", category
    return "functional", category


def wilson(success, count):
    if not count:
        return None
    z = 1.959963984540054
    proportion = success / count
    denominator = 1 + z * z / count
    midpoint = (proportion + z * z / (2 * count)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / count + z * z / (4 * count * count)) / denominator
    return [midpoint - radius, midpoint + radius]


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def median(values):
    values = [value for value in values if finite(value)]
    return statistics.median(values) if values else None


def trace_audit(row):
    path = Path(row["output_dir"]) / "choices.jsonl"
    if not path.is_file():
        return {"choices": None, "recorded_decisions": 0, "physical_actions": []}
    events = read_rows(path)
    skills = defaultdict(Counter)
    actions = Counter()
    cameras, fusion = Counter(), Counter()
    inference, http = [], []
    physical = []
    previous, consecutive, maximum = None, 0, 0
    for event in events:
        selected = event.get("selected", "")
        actions[selected] += 1
        consecutive = consecutive + 1 if selected == previous else 1
        maximum = max(maximum, consecutive)
        previous = selected
        receipt = event.get("receipt") or {}
        tool = receipt.get("tool") or selected.partition("(")[0]
        skills[tool]["attempts"] += 1
        skills[tool]["executed"] += int(receipt.get("executed") is True)
        verification = receipt.get("verification", "missing")
        skills[tool]["verification/" + verification] += 1
        skills[tool]["effect/" + receipt.get("effect", "missing")] += 1
        if receipt.get("measurement") is not None:
            skills[tool]["measurement_present"] += 1
        chunks = max(int(receipt.get("chunks", 0) or 0),
                     int((receipt.get("primitive_result") or {}).get("chunks_used", 0) or 0))
        steps = sum(int(evidence.get("steps_used", 0) or 0)
                    for evidence in event.get("motion_evidence", []) if isinstance(evidence, dict))
        if chunks or steps:
            physical.append({"decision": event.get("decision"), "selected": selected,
                             "executed_chunks": chunks, "executed_motion_steps": steps})
        timing = event.get("timing_s") or {}
        if timing.get("decision_inference_kind") == "server_compute":
            inference.append(timing.get("model_inference"))
        http.append(timing.get("http_round_trip"))
        for name in ("perception_measurement_evidence", "post_perception_measurement_evidence"):
            for evidence in (event.get(name) or {}).values():
                if isinstance(evidence, dict):
                    fusion[evidence.get("fusion_version", "missing")] += 1
                    cameras.update(evidence.get("source_cameras", []))
    return {"choices": ref(path), "recorded_decisions": len(events),
            "physical_actions": physical, "skills": {name: dict(counts) for name, counts in sorted(skills.items())},
            "maximum_consecutive_same_action": maximum,
            "maximum_same_action_total": max(actions.values(), default=0),
            "action_counts": dict(actions), "fusion_version_measurement_counts": dict(fusion),
            "source_camera_measurement_counts": dict(cameras),
            "server_compute_timed_decisions": len([value for value in inference if finite(value)]),
            "server_compute_s_total": (sum(inference)
                if events and len(inference) == len(events) and all(finite(value) for value in inference)
                else None),
            "server_compute_s_median": median(inference), "http_round_trip_s_median": median(http),
            "failure_evidence": {"failed_verifications": sum(c.get("verification/failed", 0) for c in skills.values()),
                "execution_errors": sum(c.get("verification/execution_error", 0) for c in skills.values()),
                "no_effect_actions": sum(c.get("effect/no_effect", 0) for c in skills.values()),
                "unmeasured_actions": sum(c.get("verification/unmeasured", 0) for c in skills.values())},
            "causal_root_reason": "not inferred from budget termination alone"}


def annotate(row, ledger_ref, origin):
    group, category = classify(row["result"])
    return {**row, "ledger": ledger_ref, "origin": origin, "accounting_group": group,
            "accounting_category": category, "trace": trace_audit(row)}


def group_report(rows, registered):
    functional = [row for row in rows if row.get("accounting_group") == "functional"]
    success = sum(row["result"].get("official_success") is True for row in functional)
    pending = registered - len(functional)
    return {"registered": registered, "effective_outcomes": len(functional), "successes": success,
            "functional_failures": len(functional) - success, "pending": pending,
            "final_success_rate": success / registered if not pending else None,
            "observed_success_rate": success / len(functional) if functional else None,
            "observed_wilson95": wilson(success, len(functional)),
            "full_cohort_rate_bounds_while_pending": [success / registered, (success + pending) / registered],
            "termination_categories": dict(Counter(row["accounting_category"] for row in functional)),
            "wall_s_median": median([row["result"].get("wall_s") for row in functional]),
            "server_compute_s_per_episode_median": median([row["trace"]["server_compute_s_total"] for row in functional]),
            "maximum_consecutive_same_action": max((row["trace"]["maximum_consecutive_same_action"] for row in functional), default=0),
            "episodes_with_consecutive_repeat_ge20": sum(row["trace"]["maximum_consecutive_same_action"] >= 20 for row in functional),
            "episodes_with_same_action_total_ge20": sum(row["trace"]["maximum_same_action_total"] >= 20 for row in functional)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remaining-job", default="4568")
    parser.add_argument("--startup-job", default="4567")
    parser.add_argument("--retry-ledger", action="append", type=Path, default=[])
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    cohort = root / "results/harness_v5/interim574_20261007"
    registration_path = cohort / "preparation/manifest.json"
    registration = json.loads(registration_path.read_text())
    plans = [json.loads(pinned(item).read_text()) for item in registration["files"]
             if Path(item["path"]).name.startswith("A3-N_part")]
    episodes = [episode for plan in plans for episode in plan["episodes"]]
    expected = {key(episode) for episode in episodes}
    if len(episodes) != 80 or len(expected) != 80:
        raise ValueError("The original registration must contain exactly 80 unique identities")
    preserved_path = cohort / "preparation/A3_resume_legal_r2_20261008/preserved_attempt_audit.json"
    preserved = json.loads(preserved_path.read_text())
    effective, originals, references = {}, {}, [ref(registration_path), ref(preserved_path)]
    for item in preserved["preserved_rows"]:
        identity = key(item["episode"])
        rows = [row for row in read_rows(pinned(item["ledger"])) if key(row["episode"]) == identity]
        if len(rows) != 1 or identity in originals:
            raise ValueError("Original attempts must be uniquely pinned")
        row = annotate(rows[0], item["ledger"], "preserved_original14")
        originals[identity] = row
        if row["accounting_group"] == "functional":
            effective[identity] = row
    infrastructure = {identity: row for identity, row in originals.items() if row["accounting_group"] == "infrastructure"}
    if len(originals) != 14 or len(infrastructure) != 3:
        raise ValueError("Expected the registered original14, including three boolean serialization faults")
    contract_path = cohort / f"A3-N/startup_preflight/job{args.startup_job}/part0/startup_contract.json"
    contract = json.loads(contract_path.read_text())
    startup_ledger = pinned(contract["episodes"])
    if contract.get("status") != "pass" or not contract.get("physical_actions"):
        raise ValueError("The remaining cohort needs its same-source physical startup contract")
    ledgers = [startup_ledger, *sorted((cohort / f"A3-N/job{args.remaining_job}").glob("part*/probe/episodes.jsonl"))]
    remaining_plan = cohort / "preparation/A3_resume_legal_r2_20261008/manifest.json"
    remaining_index = json.loads(remaining_plan.read_text())
    remaining_episodes = [episode for item in remaining_index["files"]
                          for episode in json.loads(pinned(item).read_text())["episodes"]]
    remaining_identities = {key(episode) for episode in remaining_episodes}
    if len(remaining_identities) != 66 or remaining_identities & originals.keys() or remaining_identities | originals.keys() != expected:
        raise ValueError("Preserved14 and remaining66 do not exactly partition the original80")
    references += [ref(contract_path), ref(remaining_plan)]
    actual_remaining = set()
    unresolved = []
    for ledger in ledgers:
        ledger_ref = ref(ledger)
        references.append(ledger_ref)
        for raw in read_rows(ledger):
            identity = key(raw["episode"])
            if identity not in remaining_identities or identity in actual_remaining:
                raise ValueError(f"Unexpected or duplicated remainder identity: {identity}")
            actual_remaining.add(identity)
            row = annotate(raw, ledger_ref, "remaining66_same_source")
            if row["accounting_group"] == "functional":
                effective[identity] = row
            else:
                unresolved.append(row)
    retries = {}
    for ledger in args.retry_ledger:
        ledger_ref = ref(ledger)
        references.append(ledger_ref)
        for raw in read_rows(ledger):
            identity = key(raw["episode"])
            if identity not in infrastructure or identity in retries:
                raise ValueError("Only one registered retry for each original boolean serialization identity")
            row = annotate(raw, ledger_ref, "once_only_infrastructure_retry")
            row["original_infrastructure_attempt"] = infrastructure[identity]
            retries[identity] = row
            if row["accounting_group"] == "functional":
                effective[identity] = row
            else:
                unresolved.append(row)
    ledger_rows = []
    for episode in episodes:
        identity = key(episode)
        if identity in effective:
            ledger_rows.append(effective[identity])
        else:
            ledger_rows.append({"episode": episode, "accounting_group": "pending",
                "accounting_category": "infra_retry_pending" if identity in infrastructure else "remaining_episode_pending",
                "original_infrastructure_attempt": infrastructure.get(identity),
                "retry_attempt": retries.get(identity), "official_success": None})
    baseline_path = root / "results/harness_v5/freeze447_repaired_report_20261005/job3427/index.json"
    baseline_index = json.loads(baseline_path.read_text())
    baseline = {}
    for group in ("A3-place5-old40", "A3-place5-new41"):
        registration_ref = baseline_index["groups"][group]["manifest"]
        pinned(registration_ref)
        references.append(registration_ref)
        for item in baseline_index["groups"][group]["results"]:
            references.append(item)
            for row in read_rows(pinned(item)):
                identity = key(row["episode"])
                if identity in baseline:
                    raise ValueError("Duplicate historical baseline identity")
                baseline[identity] = {"episode": row["episode"], "official_success": row["result"].get("official_success") is True,
                                      "output_dir": row["output_dir"], "ledger": item}
    if set(baseline) != expected or sum(row["official_success"] for row in baseline.values()) != 46:
        raise ValueError("Historical A3 must be the pinned 46/80 registration")
    paired = []
    for identity, current in effective.items():
        previous = baseline[identity]
        old, new = previous["official_success"], current["result"].get("official_success") is True
        transition = ("success" if old else "failure") + "_to_" + ("success" if new else "failure")
        paired.append({"episode": current["episode"], "transition": transition,
            "historical": previous, "current_output_dir": current["output_dir"],
            "current_termination_category": current["accounting_category"],
            "trace": current["trace"] if old != new else None})
    extra_audits = {}
    for job, label in (("4480", "development_duplicates"), ("4390", "execution_and_finalization_faults")):
        extra = []
        for ledger in sorted((cohort / f"A3-N/job{job}").glob("part*/probe/episodes.jsonl")):
            ledger_ref = ref(ledger)
            for raw in read_rows(ledger):
                row = annotate(raw, ledger_ref, label)
                row["excluded_from_once_ledger"] = True
                row["overlaps_effective_identity"] = key(raw["episode"]) in effective
                row["result_json_present"] = (Path(raw["output_dir"]) / "result.json").is_file()
                extra.append(row)
        extra_audits[label] = extra
    by_suite, by_seed = {}, {}
    for suite in sorted({episode["suite"] for episode in episodes}):
        by_suite[suite] = group_report([row for row in ledger_rows if row["episode"]["suite"] == suite], 10)
    for seed in (40, 41):
        by_seed[str(seed)] = group_report([row for row in ledger_rows if row["episode"]["seed"] == seed], 40)
    sources = Counter(str(Path(row["result"].get("source_hash_paths", {}).get("harness_v5_eval.py", "unknown")).parent)
                      for row in effective.values())
    summary = {"cohort": "A3-N interim; not behavior-freeze evidence", "internal_threshold_wording": "internal acceptance only",
        "metric": "official physical success; correct_finish remains secondary", "accounting_policy": "original functional results preserved; only three pinned bool serialization identities retried once; no best-of duplicates",
        "original_registration": ref(registration_path), "preserved_original_attempts": len(originals),
        "preserved_original_functional": len(originals) - len(infrastructure),
        "original_infrastructure_attempts": len(infrastructure), "remaining66_outcomes_present": len(actual_remaining),
        "infra_retries_present": len(retries), "unresolved_actual_attempts": unresolved,
        "total": group_report(ledger_rows, 80), "by_suite": by_suite, "by_seed": by_seed,
        "mixed_source_effective_counts": dict(sources), "mixed_source_warning": "original14 used startup_r4; remaining66 and once-only retries use legal_r2; interpret as interim developer comparison",
        "pairing": {"baseline_successes": 46, "baseline_registered": 80, "paired_observed": len(paired),
            "transitions": dict(Counter(row["transition"] for row in paired)),
            "flips": [row for row in paired if row["transition"] in ("success_to_failure", "failure_to_success")]},
        "extra_run_audit_counts": {label: {"rows": len(rows), "rows_with_physical_actions": sum(bool(row["trace"]["physical_actions"]) for row in rows),
            "recorded_physical_actions": sum(len(row["trace"]["physical_actions"]) for row in rows),
            "rows_with_official_success_in_trace": sum(any(event.get("official_success") is True for event in read_rows(Path(row["output_dir"]) / "choices.jsonl"))
                for row in rows if (Path(row["output_dir"]) / "choices.jsonl").is_file())} for label, rows in extra_audits.items()},
        "all_failures_retained": True, "PRO_output_enters_training": False}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    outputs = []
    for name, payload in (("summary.json", summary), ("paired80.json", paired), ("extra_runs_audit.json", extra_audits)):
        path = out / name
        path.write_text(json.dumps(payload, indent=2) + "\n")
        outputs.append(ref(path))
    path = out / "once80.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in ledger_rows))
    outputs.append(ref(path))
    report = ["# A3 registered 80 identity accounting", "", json.dumps(summary["total"], indent=2), "",
        "Original14 = 11 retained functional outcomes + 3 serialization infrastructure attempts.",
        f"Remaining66: {len(actual_remaining)} terminal rows present, with startup job{args.startup_job} counted once.",
        "over_token is retained as a functional failure. 4480 and 4390 never replace the once ledger.", "",
        "|Suite|Success/effective|Pending|Wilson95 on observed outcomes|", "|---|---:|---:|---|"]
    for suite, item in by_suite.items():
        report.append(f"|{suite}|{item['successes']}/{item['effective_outcomes']}|{item['pending']}|{item['observed_wilson95']}|")
    report += ["", "Pending identities:", *[json.dumps(row["episode"]) + " " + row["accounting_category"]
                    for row in ledger_rows if row["accounting_group"] == "pending"], "",
               "Trace counts are evidence summaries, not a substitute for causal failure diagnosis."]
    report_path = out / "report.md"
    report_path.write_text("\n".join(report) + "\n")
    outputs.append(ref(report_path))
    manifest = {"generator": ref(__file__), "references": [*references, ref(baseline_path)],
                "outputs": outputs, "GPU_submitted": False, "complete": summary["total"]["pending"] == 0}
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest_path), "total": summary["total"], "pairing": summary["pairing"]["transitions"]}))


if __name__ == "__main__":
    main()
