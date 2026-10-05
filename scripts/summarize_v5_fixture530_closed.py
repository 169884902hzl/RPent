"""Summarize explicit closed records from fixture526 or full-chunk stove523.

No artifact discovery, physics execution, truth-based controller or filled-in
results. Select shards explicitly. A prefix mode admits only complete saved
records and reports the planned remainder. Public verdicts are recomputed by
the supplied source's measured endpoint functions; private dual predicates
remain labels and an already satisfied endpoint is not a new achievement.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import inspect
import json
import math
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    p, div = successes / trials, 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / div
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / div
    return [centre - half, centre + half]


def transition(before, after):
    if not isinstance(before, bool) or not isinstance(after, bool):
        return "unknown"
    if before:
        return "already_satisfied_preserved" if after else "already_satisfied_destroyed"
    return "new_requested_endpoint" if after else "requested_endpoint_not_reached"


def bool_label(value):
    return value if isinstance(value, bool) else None


def confusion(pairs):
    counts = Counter()
    for truth, predicted in pairs:
        truth, predicted = bool_label(truth), bool_label(predicted)
        if truth is None:
            counts["unknown_truth"] += 1
        elif predicted is None:
            counts["unknown_public_verdict"] += 1
            counts["unknown_on_positive_truth" if truth else "unknown_on_negative_truth"] += 1
        else:
            counts["TP" if truth and predicted else "FN" if truth else "FP" if predicted else "TN"] += 1
    compared = sum(counts[k] for k in ("TP", "TN", "FP", "FN"))
    positive, negative = counts["TP"] + counts["FN"], counts["FP"] + counts["TN"]
    called_positive = counts["TP"] + counts["FP"]
    return {"counts": dict(counts), "all_pairs": len(pairs) if isinstance(pairs, list) else None,
        "compared": compared, "agreement": (counts["TP"] + counts["TN"]) / compared if compared else None,
        "agreement_wilson95": wilson(counts["TP"] + counts["TN"], compared),
        "precision": counts["TP"] / called_positive if called_positive else None,
        "recall_among_nonunknown": counts["TP"] / positive if positive else None,
        "false_positive": {"count": counts["FP"], "negative_denominator": negative,
            "rate": counts["FP"] / negative if negative else None},
        "false_negative": {"count": counts["FN"], "positive_denominator": positive,
            "rate": counts["FN"] / positive if positive else None},
        "unknown_is_not_false": True}


class Artifacts:
    def __init__(self):
        self.files, self.issues = {}, []

    def read_path(self, path, expected=None):
        path = Path(path)
        name = str(path)
        if name not in self.files:
            self.files[name] = {"sha256": sha(path), "expected_sha256": expected}
        actual = self.files[name]["sha256"]
        if expected is not None and actual != expected:
            self.issues.append({"path": name, "issue": "hash_mismatch", "expected": expected, "actual": actual})
        return path

    def ref(self, ref):
        return self.read_path(ref["path"], ref["sha256"])

    def json_ref(self, ref):
        return json.loads(self.ref(ref).read_text())

    def json_path(self, path):
        return json.loads(self.read_path(path).read_text())


def motion_summary(motions, scope):
    chunks = [m for m in motions if m.get("name") == "vla_act_chunk"]
    pairs = Counter((m.get("requested_action_count"), m.get("executed_action_count")) for m in chunks)
    requested = sum(int(m.get("requested_action_count", 0)) for m in chunks)
    executed = sum(int(m.get("executed_action_count", 0)) for m in chunks)
    # Servo and release steps are distinct from policy action chunks.
    total = sum(int(m.get("executed_action_count", m.get("steps_used", 0))) for m in motions)
    issues = []
    if scope is None:
        issues.append("registered_full_chunk_scope_missing")
    elif (scope["requested_controls"] != requested or scope["executed_controls"] != executed
          or scope["chunks_requested"] != len(chunks)):
        issues.append("scope_and_motion_trace_control_counts_differ")
    truncated = bool(scope and scope.get("external_truncation"))
    if any(a != 5 or b != 5 for a, b in pairs) and not truncated:
        issues.append("nonfive_chunk_without_external_truncation")
    return {"vla_chunks": len(chunks), "requested_vla_controls": requested,
        "executed_vla_controls": executed, "all_skill_controls_including_motion": total,
        "chunk_pairs": [{"requested": a, "executed": b, "count": n} for (a, b), n in pairs.items()],
        "raw_native_success_controls": scope.get("raw_native_success_controls") if scope else None,
        "external_truncation": truncated, "scope": scope, "issues": issues}


def dual_truth(labels):
    requested, opposite = labels.get("requested", {}), labels.get("opposite", {})
    return {"requested": bool_label(requested.get("satisfied")),
            "opposite": bool_label(opposite.get("satisfied")),
            "requested_qpos": requested.get("joint_qpos"), "opposite_qpos": opposite.get("joint_qpos")}


def private_state(truth):
    requested, opposite = truth["requested"], truth["opposite"]
    if not isinstance(requested, bool) or not isinstance(opposite, bool):
        return "unknown"
    return "both_true" if requested and opposite else "requested_only" if requested else (
        "opposite_only" if opposite else "neither_endpoint")


def fixture_stage(stage, case, artifacts):
    from robots.libero.v5_verification import measured_fixture_endpoint

    if stage is None:
        return {"phase": "first_attempt", "selected": None,
            "before": {"requested": None, "opposite": None}, "after": {"requested": None, "opposite": None},
            "transition": "unknown", "eligible_opposite_start": False,
            "new_requested_from_opposite": False, "recorded_public_requested": None,
            "recomputed_public_requested": None, "recomputed_public_opposite": None,
            "public_measurement_reason": "no_completed_first_attempt",
            "motion": None, "completed_stage": False}
    before = dual_truth(stage["private_requested_opposite_before"])
    after = dual_truth(stage["private_requested_opposite_after"])
    measured = stage.get("verification_measurements", {}).get("articulation", {})
    for phase in ("before", "after"):
        for kind in ("frame", "moving"):
            face = (measured.get(phase) or {}).get(kind)
            if face and face.get("path"):
                artifacts.ref(face)
    mode = case["mode"]
    opposite = "open" if mode == "close" else "close"
    verdicts, evidence = {}, {}
    for label, requested_mode in (("requested", mode), ("opposite", opposite)):
        verdicts[label], evidence[label] = measured_fixture_endpoint(
            measured.get("before"), measured.get("after"), requested_mode,
            drawer="drawer" in case["object_category"])
    eligible = before["requested"] is False and before["opposite"] is True
    receipt = stage.get("receipt", {})
    scope = stage.get("diagnostic_chunk_scope", {}).get("after")
    return {"phase": stage["phase"], "selected": stage["selected"],
        "before": before, "after": after, "before_private_state": private_state(before),
        "after_private_state": private_state(after),
        "transition": transition(before["requested"], after["requested"]),
        "eligible_opposite_start": eligible,
        "new_requested_from_opposite": eligible and after["requested"] is True,
        "recorded_public_requested": bool_label(receipt.get("articulate_verified")),
        "recomputed_public_requested": verdicts["requested"],
        "recomputed_public_opposite": verdicts["opposite"],
        "public_measurement_reason": evidence["requested"].get("reason"),
        "public_endpoint_evidence": evidence,
        "recorded_vs_recomputed_verdict_equal": bool_label(receipt.get("articulate_verified")) == verdicts["requested"],
        "receipt_verification": receipt.get("verification"), "error": receipt.get("error"),
        "registered_contact_prompts": stage.get("registered_contact_prompts", []),
        "motion": motion_summary(stage.get("motion_evidence", []), scope), "completed_stage": True}


def stove_observation(refs, artifacts):
    packet, labels = artifacts.json_ref(refs["public_measurements"]), artifacts.json_ref(refs["labels"])
    if not (packet["source_step"] == labels["source_step"] == refs["source_step"]):
        raise ValueError("stove public/private source steps differ")
    if packet["cached_support_used_as_current_visibility"]:
        raise ValueError("stove cached support was used as current visibility")
    for view in packet["views"].values():
        for ref in view["files"].values():
            artifacts.ref(ref)
        for query in view["queries"]:
            for instance in query["instances"]:
                artifacts.ref(instance["mask"])
                artifacts.ref(instance["cloud"])
    return {"packet": packet, "labels": labels["requested_predicates"], "refs": refs}


def stove_actions(row, artifacts):
    from robots.libero.v5_stove_measurement import measured_stove_endpoint

    phases = {p["phase"]: p for p in row.get("phases", [])}
    if set(phases) != {"initial", "on", "off"}:
        return [{"case": row["case"], "status": row["status"], "phase": p,
            "completed_stage": False, "transition": "unknown"} for p in ("on", "off")]
    samples = {(p, moment): stove_observation(phases[p][moment], artifacts)
               for p in ("initial", "on", "off") for moment in ("pre_recovery", "post_recovery")}
    result = []
    for phase, mode, opposite, preceding in (("on", "turn_on", "turn_off", "initial"),
                                             ("off", "turn_off", "turn_on", "on")):
        before_sample = samples[preceding, "post_recovery"]
        before = dual_truth({"requested": before_sample["labels"][mode], "opposite": before_sample["labels"][opposite]})
        attempt = phases[phase]["first_attempt"]
        motion = motion_summary(attempt.get("motion_evidence", []), attempt.get("chunk_completion_scope"))
        observations = []
        for moment in ("pre_recovery", "post_recovery"):
            after_sample = samples[phase, moment]
            after = dual_truth({"requested": after_sample["labels"][mode], "opposite": after_sample["labels"][opposite]})
            views = {}
            for camera in ("agentview", "wrist"):
                view_before = before_sample["packet"]["views"][camera]["coil_packet"]
                view_after = after_sample["packet"]["views"][camera]["coil_packet"]
                predictions, evidence = {}, {}
                for name, requested_mode in (("requested", mode), ("opposite", opposite)):
                    predictions[name], evidence[name] = measured_stove_endpoint(view_before, view_after, requested_mode)
                views[camera] = {"recomputed_public_requested": predictions["requested"],
                    "recomputed_public_opposite": predictions["opposite"], "evidence": evidence}
            eligible = before["requested"] is False and before["opposite"] is True
            observations.append({"stage": moment, "before": before, "after": after,
                "before_private_state": private_state(before), "after_private_state": private_state(after),
                "transition": transition(before["requested"], after["requested"]),
                "eligible_opposite_start": eligible,
                "new_requested_from_opposite": eligible and after["requested"] is True,
                "views": views, "source_step": after_sample["refs"]["source_step"]})
        result.append({"case": row["case"], "status": row["status"], "phase": phase,
            "mode": mode, "motion": motion, "completed_stage": True,
            "observations": observations, "recovery_changed_predicates": (
                any(observations[0]["after"][label] != observations[1]["after"][label]
                    for label in ("requested", "opposite"))),
            "first_attempt_error": attempt.get("error"),
            "public_recovery_error": phases[phase]["public_recovery"].get("error")})
    return result


def endpoint_metrics(samples):
    samples = list(samples)
    transitions = Counter(s["transition"] for s in samples)
    eligible = [s for s in samples if s.get("eligible_opposite_start")]
    successes = sum(s.get("new_requested_from_opposite") is True for s in samples)
    known = [s for s in samples if isinstance(s.get("after", {}).get("requested"), bool)]
    positives = sum(s["after"]["requested"] for s in known)
    return {"recorded_requests": len(samples), "transition_counts": dict(transitions),
        "new_endpoint_from_true_opposite": successes, "opposite_start_denominator": len(eligible),
        "new_endpoint_rate_from_opposite": successes / len(eligible) if eligible else None,
        "new_endpoint_from_opposite_wilson95": wilson(successes, len(eligible)),
        "new_endpoint_rate_all_recorded_lower_bound": successes / len(samples) if samples else None,
        "known_after_truth": len(known), "unknown_after_truth": len(samples) - len(known),
        "after_requested_true_including_initially_satisfied": positives,
        "after_requested_true_rate_known": positives / len(known) if known else None,
        "after_requested_true_wilson95": wilson(positives, len(known)),
        "after_private_state_counts": dict(Counter(s.get("after_private_state", "unknown") for s in samples)),
        "initially_satisfied_does_not_count_as_new": True,
        "interval_scope": "per explicit diagnostic arm; small/repeated-state development intervals do not qualify a confirmer"}


def read_run(manifest, manifest_sha256, job_root, shards, allow_prefix, artifacts):
    plan = json.loads(artifacts.read_path(manifest, manifest_sha256).read_text())
    fixture = plan.get("producer") == "scripts.probe_v5_fixture526_original"
    stove = plan.get("version") == "original-stove-control-measurement/2-fullchunks-dev"
    if fixture == stove:
        raise ValueError("only registered fixture526 or full-chunk stove523 is supported")
    total_shards = 3 if fixture else 4
    if len(set(shards)) != len(shards) or any(i not in range(total_shards) for i in shards):
        raise ValueError("explicit shard indices are duplicate or out of range")
    artifacts.ref(plan["base_config"])
    identities, rows, coverage = [], [], []
    for shard in shards:
        ref_path = job_root / f"source_identity_part{shard}.json"
        identity = artifacts.json_path(ref_path)
        if identity["manifest_sha256"] != manifest_sha256:
            raise ValueError("producer manifest SHA differs")
        for name, digest in identity["files"].items():
            artifacts.read_path(Path(identity["source"]) / name, digest)
        identities.append(identity)
        ledger = artifacts.read_path(job_root / f"part{shard}" / "episodes.jsonl")
        raw = ledger.read_bytes()
        if not raw.endswith(b"\n"):
            raise ValueError("ledger is empty or has an incomplete tail; no completed prefix assumed")
        members = [json.loads(line) for line in raw.splitlines() if line]
        expected = plan["cases"][shard::total_shards]
        if [r["case"] for r in members] != expected[:len(members)]:
            raise ValueError("ledger case identity/order differs from its registered shard")
        if not allow_prefix and len(members) != len(expected):
            raise ValueError("shard not complete; explicit closed-prefix mode is needed")
        coverage.append({"shard": shard, "ledger": str(ledger), "ledger_sha256": sha(ledger),
            "registered": len(expected), "closed_records": len(members), "unrecorded_remainder": len(expected)-len(members),
            "complete": len(members) == len(expected)})
        for row in members:
            if fixture:
                artifacts.read_path(Path(row["output_dir"]) / "choices.jsonl", row["choices_sha256"])
            else:
                saved = artifacts.json_path(Path(row["output_dir"]) / "episode.json")
                if saved != row:
                    raise ValueError("stove saved episode differs from closed ledger")
            rows.append(row)
    if not rows:
        raise ValueError("no closed records; do not prefill experimental results")
    return plan, "fixture526" if fixture else "stove523", rows, identities, coverage


def summarize(args):
    artifacts = Artifacts()
    plan, kind, rows, identities, coverage = read_run(args.manifest, args.manifest_sha256,
        args.job_root, args.shard, args.allow_closed_prefix, artifacts)
    samples, groups, setups, actions = [], defaultdict(list), [], []
    analysis_functions = {}
    if kind == "fixture526":
        from robots.libero.v5_verification import measured_fixture_endpoint
        analysis_functions["measured_fixture_endpoint"] = str(Path(inspect.getfile(measured_fixture_endpoint)).resolve())
        for row in rows:
            case = row["case"]
            first = fixture_stage(row.get("first_attempt"), case, artifacts)
            first.update(case=case, status=row["status"], binding_error=row.get("binding_error"),
                native_original_success_latched=row.get("native_original_success_latched"),
                external_action_budget_exhausted=row.get("external_action_budget_exhausted"))
            samples.append(first)
            groups[case["type"], case["condition"]].append(first)
            if first["motion"]:
                actions.append(first["motion"])
            for stage in row.get("setup", []):
                setup = fixture_stage(stage, case, artifacts)
                setup.update(case=case, role="fixed_real_setup_not_first_attempt")
                setups.append(setup)
    else:
        from robots.libero.v5_stove_measurement import measured_stove_endpoint
        analysis_functions["measured_stove_endpoint"] = str(Path(inspect.getfile(measured_stove_endpoint)).resolve())
        for row in rows:
            for action in stove_actions(row, artifacts):
                actions.append(action.get("motion"))
                if not action["completed_stage"]:
                    samples.append(action)
                    groups[action["phase"], "unmeasured"].append(action)
                    continue
                for observation in action["observations"]:
                    observation.update(case=action["case"], mode=action["mode"], phase=action["phase"],
                        motion=action["motion"], first_attempt_error=action["first_attempt_error"],
                        public_recovery_error=action["public_recovery_error"],
                        recovery_changed_predicates=action["recovery_changed_predicates"])
                    samples.append(observation)
                    groups[action["phase"], observation["stage"]].append(observation)
    metrics = []
    for key, group in groups.items():
        item = {"group": list(key), **endpoint_metrics(group)}
        if kind == "fixture526":
            item["dual_predicate_confusion"] = {label: confusion([
                (s.get("after", {}).get(label), s.get("recomputed_public_" + label)) for s in group])
                for label in ("requested", "opposite")}
            item["original_receipt_requested_confusion"] = confusion([
                (s.get("after", {}).get("requested"), s.get("recorded_public_requested")) for s in group])
            item["receipt_recomputed_mismatches"] = sum(s.get("recorded_vs_recomputed_verdict_equal") is False for s in group)
        else:
            item["dual_predicate_confusion_by_view"] = {camera: {label: confusion([
                (s.get("after", {}).get(label), s.get("views", {}).get(camera, {}).get("recomputed_public_" + label))
                for s in group]) for label in ("requested", "opposite")}
                for camera in ("agentview", "wrist")}
        metrics.append(item)
    control_issues = [a for a in actions if a and a["issues"]]
    analysis_sources = []
    for name, path in analysis_functions.items():
        relative = ("robots/libero/v5_verification.py" if name == "measured_fixture_endpoint"
                    else "robots/libero/v5_stove_measurement.py")
        digest = sha(path)
        expected = {i["files"].get(relative) for i in identities}
        if expected != {digest}:
            artifacts.issues.append({"path": path, "issue": "analysis_verifier_differs_from_producer_snapshot",
                "actual": digest, "producer_expected_sha256": sorted(str(v) for v in expected)})
        analysis_sources.append({"function": name, "path": path, "sha256": digest,
            "matches_registered_producer": expected == {digest}})
    report = {"kind": kind, "manifest": {"path": str(args.manifest), "sha256": args.manifest_sha256},
        "job_root": str(args.job_root), "source_identities": identities,
        "coverage": coverage, "planned_episodes_all_shards": len(plan["cases"]),
        "closed_episode_records": len(rows), "all_registered_shards_complete": (
            len(coverage) == (3 if kind == "fixture526" else 4) and all(c["complete"] for c in coverage)),
        "closed_prefix_not_final_result": args.allow_closed_prefix,
        "metrics": metrics, "setup_transitions": dict(Counter(s["transition"] for s in setups)),
        "native_original_success_latched_episodes": sum(bool(r.get("native_original_success_latched", False)) for r in rows),
        "external_action_budget_exhausted_episodes": sum(bool(r.get("external_action_budget_exhausted", False)) for r in rows),
        "control_trace_records": len([a for a in actions if a]),
        "control_trace_issues": control_issues,
        "analysis_source_files": analysis_sources,
        "artifact_files_hashed": len(artifacts.files), "artifact_integrity_issues": artifacts.issues,
        "development_only_not_qualification": True, "new_training_rows": sum(r["new_training_rows"] for r in rows),
        "truth_never_used_for_public_state_or_control": True}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("report.json", report), ("samples.json", samples), ("setups.json", setups),
                        ("artifact_sha_audit.json", artifacts.files)):
        (args.output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"kind": kind, "closed_records": len(rows), "metrics": metrics,
        "control_trace_issues": len(control_issues), "artifact_integrity_issues": len(artifacts.issues),
        "report_sha256": sha(args.output / "report.json")}, indent=2))
    if artifacts.issues or control_issues:
        raise SystemExit("closed evidence/control audit failed; saved report is not an accepted experimental result")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--shard", type=int, action="append", required=True)
    parser.add_argument("--allow-closed-prefix", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    summarize(parser.parse_args())


if __name__ == "__main__":
    main()
