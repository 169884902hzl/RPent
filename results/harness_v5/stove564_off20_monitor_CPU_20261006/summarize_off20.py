"""Inspect only the 20 manifest-listed original stove cells and their refs."""

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import time


def ref(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def wilson(successes, total):
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [centre - half, centre + half]


def read_jsonl(path, *, live):
    lines = path.read_text().splitlines()
    rows = []
    for i, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if live and i == len(lines) - 1:
                return rows, True
            raise
    return rows, False


def private_keys(value):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"joint_qpos", "requested_predicates", "sim_truth", "turn_on_satisfied", "turn_off_satisfied"}:
                found.append(k)
            found += private_keys(v)
    elif isinstance(value, list):
        for v in value:
            found += private_keys(v)
    return found


def joint_scalar(row):
    joint = row.get("joint_qpos")
    if isinstance(joint, list) and len(joint) == 1 and isinstance(joint[0], list) and len(joint[0]) == 1:
        return joint[0][0]
    return None


def public_motion_summary(stage):
    if stage is None:
        return None
    record = {k: v for k, v in stage.items() if k != "motion_evidence"}
    fields = ("name", "target_xyz", "final_eef_pos", "final_dist_m", "steps_used", "actions_used",
              "max_steps", "terminated", "truncated")
    record["motion_summary"] = [{k: motion[k] for k in fields if k in motion}
                                for motion in stage.get("motion_evidence", [])]
    record["raw_motion_evidence_retained_in_episode_json"] = True
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    for path in (args.manifest, args.run_root, args.output):
        if not path.is_absolute():
            parser.error("paths must be absolute")
    if ref(args.manifest)["sha256"] != args.expected_sha:
        raise ValueError("off20 manifest changed")
    plan = json.loads(args.manifest.read_text())
    checked, violations, cells, curves, captures = [ref(args.manifest)], [], [], [], []
    for relative, sha in plan["source_sha256"].items():
        identity = ref(Path(plan["source_root"]) / relative)
        checked.append(identity)
        if identity["sha256"] != sha:
            violations.append("immutable source SHA mismatch:" + relative)
    for identity in plan["owned_files"]:
        actual = ref(identity["path"])
        checked.append(actual)
        if actual["sha256"] != identity["sha256"]:
            violations.append("owned source SHA mismatch:" + identity["path"])
    for key in ("base_config", "design_manifest", "original_sampling_manifest", "original_task_catalog_file"):
        actual = ref(plan[key]["path"])
        checked.append(actual)
        if actual["sha256"] != plan[key]["sha256"]:
            violations.append("registered metadata SHA mismatch:" + key)
    for i in range(8):
        path = args.run_root / f"preflight_part{i}.json"
        if path.exists():
            checked.append(ref(path))
            preflight = json.loads(path.read_text())
            if (not preflight["passed"] or preflight["manifest"]["sha256"] != args.expected_sha
                    or preflight["config_overrides"] != {"dual_view_fusion_v1": True}):
                violations.append(f"part{i}:runtime preflight changed")
        elif args.complete:
            violations.append(f"part{i}:runtime preflight missing")
    for index, cell in enumerate(plan["cells"]):
        name, part = cell["name"], index % 8
        directory = args.run_root / f"part{part}" / name
        record = {"name": name, "method": cell["method"], "seed": cell["original_case"]["episode"]["seed"],
                  "state_sha256": cell["original_case"]["state_sha256"], "part": part,
                  "output_dir": str(directory), "completed": False, "infra_errors": [],
                  "on_prompt": cell["on_prompt"], "off_prompt": cell["off_prompt"]}
        for key in ("bddl", "init_file"):
            actual = ref(cell["original_case"][key]["path"])
            checked.append(actual)
            if actual["sha256"] != cell["original_case"][key]["sha256"]:
                violations.append(name + ":asset SHA mismatch:" + key)
        ledger = directory / "labels_chunk.jsonl"
        if ledger.exists():
            checked.append(ref(ledger))
            labels, partial = read_jsonl(ledger, live=not args.complete)
            record["private_score_rows"] = len(labels)
            record["partial_label_write"] = partial
            record["last_phase"] = labels[-1]["phase"] if labels else None
            record["last_chunk"] = labels[-1]["chunk_index"] if labels else None
            for label in labels:
                if label.get("status") != "scored":
                    record["infra_errors"].append({"category": "private_scoring_infrastructure", "label": label})
                curves.append({"cell": name, **label})
            record["actual_contact_chunks"] = sum(label["timing"] == "after_executed_chunk" for label in labels)
            record["phase_controls"] = {phase: max((r["actual_controls"] for r in labels if r["phase"] == phase), default=0)
                                        for phase in ("on", "off")}
        else:
            labels = []
            record.update(private_score_rows=0, actual_contact_chunks=0, phase_controls={"on": 0, "off": 0})
        episode = directory / "episode.json"
        if episode.exists():
            checked.append(ref(episode))
            row = json.loads(episode.read_text())
            record.update(completed=True, status=row["status"], wall_s=row["wall_s"],
                          native_original_success_latched=row.get("native_original_success_latched"),
                          external_action_budget_exhausted=row.get("external_action_budget_exhausted"),
                          public_refinement=public_motion_summary(row.get("public_refinement")),
                          public_recovery=public_motion_summary(row.get("public_recovery")))
            if row["status"] == "probe_error":
                record["infra_errors"].append({"category": row.get("failure_category", "probe_error"),
                                               "error": row.get("error")})
            for phase, key in (("on", "on_setup"), ("off", "off_contact")):
                attempt = row.get(key, {})
                scope = attempt.get("chunk_completion_scope", {})
                record[key] = {"prompt": attempt.get("prompt"), "receipt": attempt.get("receipt"),
                               "scope": scope, "fixed_prefix_completed": attempt.get("fixed_prefix_completed"),
                               "executed_control_actions": attempt.get("executed_control_actions"),
                               "wall_s": attempt.get("wall_s"), "status": attempt.get("status"), "error": attempt.get("error")}
                expected_prompt = cell["on_prompt"] if phase == "on" else cell["off_prompt"]
                phase_labels = [r for r in labels if r["phase"] == phase]
                complete_scope = (attempt.get("fixed_prefix_completed") is True
                                  and attempt.get("prompt") == expected_prompt
                                  and attempt.get("receipt", {}).get("chunks") == 160
                                  and scope.get("chunks_requested") == 160
                                  and scope.get("executed_controls") == 800
                                  and attempt.get("executed_control_actions") == 800
                                  and scope.get("private_joint_or_predicate_used_for_control") is False)
                complete_labels = (len(phase_labels) == 161
                                   and [r["chunk_index"] for r in phase_labels] == list(range(161))
                                   and all(r["actual_controls"] == r["chunk_index"] * 5 for r in phase_labels))
                if not complete_scope or not complete_labels:
                    record["infra_errors"].append({"category": "incomplete_contact_or_score_ledger", "phase": phase})
                points = [joint_scalar(r) for r in phase_labels]
                record[phase + "_curve_summary"] = {"first_joint": points[0] if points else None,
                    "last_joint": points[-1] if points else None,
                    "joint_delta": points[-1] - points[0] if points and all(x is not None for x in points) else None,
                    "first_true_off_chunk": next((r["chunk_index"] for r in phase_labels if r.get("turn_off_satisfied") is True), None),
                    "true_off_scored_rows": sum(r.get("turn_off_satisfied") is True for r in phase_labels),
                    "last_true_off": phase_labels[-1].get("turn_off_satisfied") if phase_labels else None}
            for stage in ("before_setup", "after_setup", "before_off", "after_contact", "post_recovery"):
                reference = row.get("captures", {}).get(stage)
                if not reference:
                    record["infra_errors"].append({"category": "capture_missing", "stage": stage})
                    continue
                public_path, label_path = Path(reference["public_measurements"]["path"]), Path(reference["labels"]["path"])
                public, truth = json.loads(public_path.read_text()), json.loads(label_path.read_text())
                for key in ("public_measurements", "labels"):
                    actual = ref(reference[key]["path"])
                    checked.append(actual)
                    if actual["sha256"] != reference[key]["sha256"]:
                        violations.append(name + ":capture SHA mismatch:" + stage + ":" + key)
                if private_keys(public):
                    violations.append(name + ":private labels in public capture:" + stage)
                cameras = list(public["views"])
                if cameras != ["agentview", "wrist"] or public["source_step"] != truth["source_step"]:
                    violations.append(name + ":public/private capture timing/views mismatch:" + stage)
                for view in public["views"].values():
                    for reference in view["files"].values():
                        actual = ref(reference["path"])
                        checked.append(actual)
                        if actual["sha256"] != reference["sha256"]:
                            violations.append(name + ":view resource SHA mismatch:" + stage)
                    for query in view["queries"]:
                        for instance in query["instances"]:
                            for key in ("mask", "cloud"):
                                if key in instance:
                                    actual = ref(instance[key]["path"])
                                    checked.append(actual)
                                    if actual["sha256"] != instance[key]["sha256"]:
                                        violations.append(name + ":SAM resource SHA mismatch:" + stage)
                info = {"cell": name, "method": cell["method"], "seed": record["seed"], "stage": stage,
                    "source_step": public["source_step"], "views": cameras,
                    "entity_fusion_config_enabled": True, "control_views_fused": public["control_views_fused"],
                    "current_shell_count": public["current_shell_count"],
                    "turn_on": truth["requested_predicates"]["turn_on"]["satisfied"],
                    "turn_off": truth["requested_predicates"]["turn_off"]["satisfied"],
                    "joint_qpos": truth["requested_predicates"]["turn_off"]["joint_qpos"],
                    "public_ref": ref(public_path), "private_ref": ref(label_path)}
                captures.append(info)
                record[stage] = {k: info[k] for k in ("source_step", "turn_on", "turn_off", "joint_qpos")}
            record["on_setup_satisfied"] = record.get("after_setup", {}).get("turn_on")
            record["turn_off_after_contact"] = record.get("after_contact", {}).get("turn_off")
            record["turn_off_after_recovery"] = record.get("post_recovery", {}).get("turn_off")
            record["valid_fixed_physical_cell"] = not record["infra_errors"]
        cells.append(record)
    completed = [c for c in cells if c["completed"]]
    valid = [c for c in completed if c.get("valid_fixed_physical_cell")]
    summaries = []
    for method in [m["id"] for m in plan["methods"]]:
        group = [c for c in valid if c["method"] == method]
        for stratum in ("all_retained", "setup_succeeded", "setup_failed"):
            selected = group if stratum == "all_retained" else [c for c in group if c["on_setup_satisfied"] == (stratum == "setup_succeeded")]
            success = sum(c["turn_off_after_recovery"] is True for c in selected)
            summaries.append({"method": method, "stratum": stratum, "n": len(selected), "off_successes": success,
                              "off_rate": success / len(selected) if selected else None,
                              "wilson95": wilson(success, len(selected)),
                              "off_after_contact_successes": sum(c["turn_off_after_contact"] is True for c in selected)})
    paired = []
    methods = [m["id"] for m in plan["methods"]]
    for first, second in itertools.combinations(methods, 2):
        pairs = []
        for seed in range(5):
            left = next((c for c in valid if c["method"] == first and c["seed"] == seed), None)
            right = next((c for c in valid if c["method"] == second and c["seed"] == seed), None)
            if left is not None and right is not None:
                pairs.append({"seed": seed, "first_off": left["turn_off_after_recovery"], "second_off": right["turn_off_after_recovery"],
                    "first_setup": left["on_setup_satisfied"], "second_setup": right["on_setup_satisfied"]})
        paired.append({"first": first, "second": second, "pairs": pairs,
            "second_only_success": sum(p["second_off"] and not p["first_off"] for p in pairs),
            "first_only_success": sum(p["first_off"] and not p["second_off"] for p in pairs),
            "same_original_state_only": True, "same_on_setup_not_guaranteed": True})
    errors = Counter(e["category"] for c in completed for e in c["infra_errors"])
    summary = {"version": "off20-fixed-original-summary/1", "job": "4303", "timestamp_unix": time.time(),
        "live_snapshot": not args.complete, "expected_cells": 20, "completed_cells": len(completed),
        "valid_physical_cells": len(valid), "infrastructure_cells": len(completed) - len(valid),
        "completed_contact_chunks": sum(c["actual_contact_chunks"] for c in cells), "expected_contact_chunks": 6400,
        "private_score_rows": sum(c["private_score_rows"] for c in cells), "expected_private_score_rows": 6440,
        "executed_contact_controls": sum(sum(c["phase_controls"].values()) for c in cells), "expected_contact_controls": 32000,
        "source_and_reference_violations": violations, "infra_error_categories": dict(errors),
        "method_and_setup_stratum_summary": summaries, "paired_method_comparisons": paired, "cells": cells,
        "capture_count": len(captures), "expected_capture_count": 100, "perception_config": {"dual_view_fusion_v1": True,
            "control_captures_are_separate_views": True, "shell_fusion_history_not_saved_by_this_runner": True},
        "qualification_authorized": False, "endpoint_qualified": False, "new_training_rows": 0,
        "interpretation": "Five original reset identities across four paired development methods; not20 independent states or confirmation. Setup failures retained with separate denominators. No endpoint threshold fitted from private truth."}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "private_chunk_curves.jsonl").write_text("".join(json.dumps(c) + "\n" for c in curves))
    (args.output / "capture_scoring_table.jsonl").write_text("".join(json.dumps(c) + "\n" for c in captures))
    (args.output / "input_manifest.json").write_text(json.dumps({"explicit_refs": checked,
        "producer": ref(Path(__file__)), "manifest_expected_sha256": args.expected_sha,
        "no_glob_or_directory_scan": True, "live_inputs_may_continue_growing": not args.complete}, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("completed_cells", "valid_physical_cells", "infrastructure_cells",
        "completed_contact_chunks", "private_score_rows", "executed_contact_controls", "source_and_reference_violations", "infra_error_categories")}))
    if args.complete and (len(completed) != 20 or len(valid) != 20 or violations
            or summary["completed_contact_chunks"] != 6400 or summary["private_score_rows"] != 6440
            or summary["executed_contact_controls"] != 32000 or len(captures) != 100):
        raise SystemExit("Preserved incomplete/invalid development run; repair or report infrastructure separately")


if __name__ == "__main__":
    main()
