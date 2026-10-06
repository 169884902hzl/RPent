"""Read only explicit registered stove4210 paths and public measurement packets."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_json(path, errors):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError) as error:
        errors.append({"path": str(path), "error": repr(error)})
        return None


def ledger_rows(path, errors):
    if not path.is_file():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except ValueError as error:
            errors.append({"path": str(path), "line": line_number, "error": repr(error)})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--job", type=int, default=4210)
    args = parser.parse_args()
    assert args.root.is_absolute() and args.manifest.is_absolute() and args.source.is_absolute()
    plan = json.loads(args.manifest.read_text())
    assert plan["planned_episodes"] == 10 and plan["stove_control_features_v1"] is True
    run = args.root / "results/harness_v5/stove555_measurement10_original_20261006" / f"probe_job{args.job}"
    errors, captures, missing, episode_results, preflights = [], [], [], [], []
    for part in range(plan["shards"]):
        preflight = read_json(run / f"preflight_part{part}.json", errors)
        if preflight is not None:
            preflights.append({"part": part, "passed": preflight["passed"],
                "manifest_sha256": preflight["manifest_sha256"], "state_hashes_checked": preflight.get("state_hashes_checked")})
        for row in ledger_rows(run / f"part{part}/episodes.jsonl", errors):
            episode_results.append({"part": part, "case": row["case"]["name"], "status": row["status"],
                "wall_s": row.get("wall_s"), "error": row.get("error"),
                "contacts": [{"phase": phase["phase"], "first_attempt": {key: phase.get("first_attempt", {}).get(key)
                    for key in ("receipt", "status", "error", "executed_control_actions", "wall_s", "chunk_completion_scope")}}
                             for phase in row.get("phases", []) if phase["mode"] is not None]})
    for index, case in enumerate(plan["cases"]):
        part = index % plan["shards"]
        for phase in plan["phases"]:
            stages = ["pre_recovery", "post_recovery"]
            if phase["mode"] is not None:
                stages.insert(0, "before_contact")
            for stage in stages:
                path = run / f"part{part}" / case["name"] / phase["name"] / stage / "public_measurements.json"
                packet = read_json(path, errors)
                if packet is None:
                    missing.append(str(path))
                    continue
                record = {"case": case["name"], "phase": phase["name"], "stage": stage,
                          "source_step": packet["source_step"], "packet": identity(path),
                          "current_shell_count": packet["current_shell_count"],
                          "parent_binding": packet.get("control_parent_binding"), "views": {}}
                for camera in plan["capture_views"]:
                    view = packet["views"].get(camera)
                    if view is None:
                        continue
                    feature = view.get("control_features", {})
                    queries = []
                    for query in view["queries"]:
                        instances = query["instances"]
                        queries.append({"role": query.get("feature_role", "control"), "prompt": query["prompt"],
                            "instances": len(instances), "points": sum(x.get("valid_depth_points", 0) for x in instances),
                            "instance_reasons": dict(Counter(x.get("binding", {}).get("reason", x.get("reason", "not_bound"))
                                                           for x in instances)),
                            "instance_clouds": [x["cloud"] for x in instances if "cloud" in x]})
                    record["views"][camera] = {"source_step": view["source_step"],
                        "parent": feature.get("parent"), "control_pose_measured": bool(feature.get("control_pose")),
                        "valid_control_candidates": feature.get("valid_control_candidates"),
                        "directed_lever_measured": bool(feature.get("directed_lever")),
                        "stove_reference_measured": bool(feature.get("stove_reference")),
                        "signed_angle_measured": feature.get("signed_angle_to_reference_deg") is not None,
                        "endpoint_state": feature.get("endpoint_state"), "reason": feature.get("reason"),
                        "feature_binding": feature.get("feature_binding"), "queries": queries,
                        "rgbd_metadata": view["files"]}
                record["same_capture_two_view_evidence"] = bool(
                    set(record["views"]) == set(plan["capture_views"])
                    and all(v["source_step"] == record["source_step"] for v in record["views"].values()))
                record["both_views_control_measured"] = bool(record["same_capture_two_view_evidence"]
                    and all(v["control_pose_measured"] for v in record["views"].values()))
                record["both_views_directed_features_measured"] = bool(record["same_capture_two_view_evidence"]
                    and all(v["directed_lever_measured"] and v["stove_reference_measured"]
                            for v in record["views"].values()))
                captures.append(record)
    view_summary = {}
    for camera in plan["capture_views"]:
        views = [record["views"][camera] for record in captures if camera in record["views"]]
        role_counts = {}
        for role in ("control", "pivot", "tip", "shell", "front_edge"):
            queries = [query for view in views for query in view["queries"] if query["role"] == role]
            reasons = Counter()
            for query in queries:
                reasons.update(query["instance_reasons"])
            role_counts[role] = {"queries": len(queries), "queries_with_any_instance": sum(q["instances"] > 0 for q in queries),
                "instances": sum(q["instances"] for q in queries), "points": sum(q["points"] for q in queries),
                "instance_reasons": dict(reasons)}
        view_summary[camera] = {"captured_views": len(views),
            **{key: sum(v[key] for v in views) for key in ("control_pose_measured", "directed_lever_measured",
                                                        "stove_reference_measured", "signed_angle_measured")},
            "endpoint_states": dict(Counter(v["endpoint_state"] for v in views)),
            "binding_reasons": dict(Counter(v["reason"] for v in views)), "roles": role_counts}
    squeue = subprocess.run(["squeue", "-j", str(args.job), "-h", "-o", "%i|%T|%M|%R"],
                            capture_output=True, text=True, check=False)
    source = []
    for name, expected in plan["required_source_sha256"].items():
        actual = identity(args.source / name)
        source.append({**actual, "matches_registered": actual["sha256"] == expected})
    report = {"observed_utc": datetime.now(timezone.utc).isoformat(), "job": args.job,
        "scope": "Read-only explicit original manifest outputs; public geometry coverage, not ground-truth recall or endpoint qualification",
        "manifest": identity(args.manifest), "run": str(run), "source_files": source,
        "squeue": squeue.stdout.splitlines(), "squeue_error": squeue.stderr, "preflights": preflights,
        "completed_episodes": len(episode_results), "episode_statuses": dict(Counter(r["status"] for r in episode_results)),
        "expected_captures": plan["planned_measurement_captures"], "captured_packets": len(captures),
        "same_capture_two_view_evidence": sum(r["same_capture_two_view_evidence"] for r in captures),
        "both_views_control_measured": sum(r["both_views_control_measured"] for r in captures),
        "both_views_directed_features_measured": sum(r["both_views_directed_features_measured"] for r in captures),
        "per_camera": view_summary, "episodes": episode_results, "captures": captures,
        "missing_expected_capture_paths": missing, "read_errors": errors,
        "nearzero_public_measurement_prerequisite_met": bool(captures and any(
            view["directed_lever_measured"] and view["stove_reference_measured"]
            for record in captures for view in record["views"].values())),
        "qualification_authorized": False, "gpu_submitted": False}
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
