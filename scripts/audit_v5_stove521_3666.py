"""Audit explicitly referenced stove521 evidence; private labels stay diagnostic.

This script opens only the supplied manifest, its four registered shard ledgers,
source identities, and artifact references found in those ledgers/packets.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flatten(values):
    if isinstance(values, list):
        return [n for value in values for n in flatten(value)]
    return [values]


def audit(manifest_path, job_root, output):
    from robots.libero.v5_stove_measurement import measured_stove_endpoint

    plan = json.loads(manifest_path.read_text())
    if plan["version"] not in ("original-stove-control-measurement/1-dev", "original-stove-control-measurement/2-fullchunks-dev") or plan["shards"] != 4:
        raise ValueError("unexpected explicitly registered measurement protocol")
    output.mkdir(parents=True, exist_ok=False)
    checked, issues, source_identities = {}, [], []

    def verify(ref):
        path = str(ref["path"])
        if path not in checked:
            actual = sha(path)
            checked[path] = {"sha256": actual, "expected_sha256": ref["sha256"],
                             "matches": actual == ref["sha256"]}
        elif checked[path]["expected_sha256"] != ref["sha256"]:
            issues.append({"path": path, "issue": "conflicting_reference_hash"})
        if not checked[path]["matches"]:
            issues.append({"path": path, "issue": "sha_mismatch"})
        return Path(path)

    verify(plan["base_config"])
    observations, episodes, actions = [], [], []
    queries = Counter()
    coil_labels = Counter()
    verdicts = Counter()
    coil_packets = {}
    for index in range(4):
        identity_path = job_root / f"source_identity_part{index}.json"
        identity = json.loads(identity_path.read_text())
        if identity["manifest_sha256"] != sha(manifest_path):
            issues.append({"shard": index, "issue": "manifest_hash_mismatch"})
        for name, expected in identity["files"].items():
            verify({"path": str(Path(identity["source"]) / name), "sha256": expected})
        source_identities.append({"path": str(identity_path), "sha256": sha(identity_path), **identity})
        ledger_path = job_root / f"part{index}" / "episodes.jsonl"
        rows = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        expected = plan["cases"][index::4]
        if [row["case"] for row in rows] != expected:
            issues.append({"shard": index, "issue": "case_identity_or_coverage_mismatch"})
        for row in rows:
            seed = row["case"]["episode"]["seed"]
            episodes.append({"seed": seed, "status": row["status"],
                "native_original_success_latched": row["native_original_success_latched"],
                "external_action_budget_exhausted": row["external_action_budget_exhausted"],
                "wall_s": row["wall_s"], "new_training_rows": row["new_training_rows"]})
            for phase in row["phases"]:
                attempt = phase["first_attempt"]
                if attempt:
                    actions.append({"seed": seed, "phase": phase["phase"],
                        "receipt": attempt.get("receipt"), "status": attempt.get("status"),
                        "error": attempt.get("error"),
                        "executed_control_actions": attempt.get("executed_control_actions"),
                        "requested_control_actions": sum(m.get("requested_action_count", 0) for m in attempt.get("motion_evidence", [])),
                        "chunk_action_pairs": dict(Counter(
                            f"{m.get('requested_action_count')}->{m.get('executed_action_count')}"
                            for m in attempt.get("motion_evidence", []) if m.get("name") == "vla_act_chunk")),
                        "chunk_completion_scope": attempt.get("chunk_completion_scope"),
                        "wall_s": attempt.get("wall_s"),
                        "recovery_status": phase["public_recovery"].get("status", "executed"),
                        "recovery_error": phase["public_recovery"].get("error")})
                for stage in ("pre_recovery", "post_recovery"):
                    refs = phase[stage]
                    packet = json.loads(verify(refs["public_measurements"]).read_text())
                    labels = json.loads(verify(refs["labels"]).read_text())
                    if packet["source_step"] != labels["source_step"] or packet["source_step"] != refs["source_step"]:
                        issues.append({"seed": seed, "phase": phase["phase"], "stage": stage,
                                       "issue": "measurement_label_step_mismatch"})
                    if packet["cached_support_used_as_current_visibility"]:
                        issues.append({"seed": seed, "issue": "cached_support_used_as_current_visibility"})
                    truth = labels["requested_predicates"]
                    label_summary = {"turn_on": truth["turn_on"]["satisfied"],
                                     "turn_off": truth["turn_off"]["satisfied"],
                                     "qpos": flatten(truth["turn_on"]["joint_qpos"])}
                    view_summaries = {}
                    for camera, view in packet["views"].items():
                        for ref in view["files"].values():
                            verify(ref)
                        instance_summaries = []
                        for query in view["queries"]:
                            queries[(stage, camera, query["prompt"], "queries")] += 1
                            queries[(stage, camera, query["prompt"], "instances")] += len(query["instances"])
                            for instance in query["instances"]:
                                verify(instance["mask"])
                                verify(instance["cloud"])
                                instance_summaries.append({"query": query["prompt"],
                                    **{key: instance[key] for key in ("id", "score", "mask_pixels", "valid_depth_points",
                                                                   "valid_depth_fraction", "geometry")}})
                        coil = view["coil_packet"]
                        key = (seed, phase["phase"], stage, camera)
                        coil_packets[key] = coil
                        if coil:
                            coil_labels[(camera, stage, coil["state"], label_summary["turn_on"], label_summary["turn_off"])] += 1
                        view_summaries[camera] = {"instances": instance_summaries,
                            "files": view["files"], "coil": None if coil is None else {
                                k: coil.get(k) for k in ("version", "source_step", "visible", "state", "reason", "features")}}
                    observations.append({"seed": seed, "phase": phase["phase"], "stage": stage,
                        "source_step": refs["source_step"], "labels": label_summary,
                        "current_stove_shell": packet["current_stove_shell"],
                        "current_shell_count": packet["current_shell_count"],
                        "public_packet": refs["public_measurements"], "label_packet": refs["labels"],
                        "views": view_summaries})
            # Test actual on->off observations with the conservative existing verifier.
            for stage in ("pre_recovery", "post_recovery"):
                for camera in ("agentview", "wrist"):
                    verified, evidence = measured_stove_endpoint(
                        coil_packets[(seed, "on", stage, camera)],
                        coil_packets[(seed, "off", stage, camera)], "turn_off")
                    verdicts[(stage, camera, str(verified), evidence["reason"])] += 1
    by_key = {(row["seed"], row["phase"], row["stage"]): row for row in observations}
    end_states = []
    recovery_changes = []
    for case in plan["cases"]:
        seed = case["episode"]["seed"]
        for phase in ("initial", "on", "off"):
            pre = by_key[(seed, phase, "pre_recovery")]["labels"]
            post = by_key[(seed, phase, "post_recovery")]["labels"]
            end_states.append({"seed": seed, "phase": phase, "pre": pre, "post": post})
            if pre["turn_on"] != post["turn_on"] or pre["turn_off"] != post["turn_off"]:
                recovery_changes.append({"seed": seed, "phase": phase, "pre": pre, "post": post})
    report = {"scope": "original_task_stove_diagnostic_only_not_freeze_or_training",
        "manifest": {"path": str(manifest_path), "sha256": sha(manifest_path)},
        "job_root": str(job_root), "episodes": len(episodes), "contact_skills": len(actions),
        "observations": len(observations), "view_packets": len(observations) * 2,
        "query_count": sum(count for key, count in queries.items() if key[-1] == "queries"),
        "query_instances": sum(count for key, count in queries.items() if key[-1] == "instances"),
        "query_counts": [{"stage": stage, "camera": camera, "prompt": prompt, "metric": metric, "count": count}
                         for (stage, camera, prompt, metric), count in sorted(queries.items())],
        "coil_label_counts": [{"camera": camera, "stage": stage, "coil_state": state,
                               "truth_on": on, "truth_off": off, "count": count}
                              for (camera, stage, state, on, off), count in sorted(coil_labels.items())],
        "off_verdict_counts": [{"stage": stage, "camera": camera, "verified": verdict,
                                "reason": reason, "count": count}
                               for (stage, camera, verdict, reason), count in sorted(verdicts.items())],
        "shell_measured_observations": sum(row["current_shell_count"] == 1 for row in observations),
        "native_original_success_latched": sum(row["native_original_success_latched"] for row in episodes),
        "macro_execution_errors": sum(row["status"] == "execution_error" for row in actions),
        "public_recovery_errors": sum(row["recovery_status"] == "execution_error" for row in actions),
        "macro_chunks": [row["receipt"].get("chunks") for row in actions if row["receipt"]],
        "actual_controls_by_phase": {phase: [row["executed_control_actions"] for row in actions if row["phase"] == phase]
                                     for phase in ("on", "off")},
        "actual_macro_endpoints": {phase: {stage: {
            "truth_on": sum(row["labels"]["turn_on"] for row in observations if row["phase"] == phase and row["stage"] == stage),
            "truth_off": sum(row["labels"]["turn_off"] for row in observations if row["phase"] == phase and row["stage"] == stage)}
            for stage in ("pre_recovery", "post_recovery")} for phase in ("initial", "on", "off")},
        "recovery_changed_predicate": recovery_changes,
        "artifact_files_checked": len(checked), "artifact_hash_mismatches": sum(not r["matches"] for r in checked.values()),
        "issues": issues, "new_training_rows": sum(row["new_training_rows"] for row in episodes),
        "qualification_authorized": False}
    artifacts = {"report.json": report, "observations.json": observations,
                 "endpoint_pairs.json": end_states, "actions.json": actions,
                 "episodes.json": episodes, "artifact_sha_audit.json": checked,
                 "source_identities.json": source_identities}
    for name, value in artifacts.items():
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))
    if issues:
        raise SystemExit("referenced evidence integrity audit failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.manifest, args.job_root, args.output)


if __name__ == "__main__":
    main()
