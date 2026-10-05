"""Audit the twelve explicit original fixture trials, including setup regressions."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_qpos(label):
    value = label.get("joint_qpos")
    while isinstance(value, list) and value:
        value = value[0]
    return value


def transition(before, after):
    if before is None or after is None:
        return "not_measured"
    return ("new_requested_endpoint" if after else "requested_endpoint_not_reached") if not before else (
        "already_satisfied_preserved" if after else "already_satisfied_destroyed")


def audit(manifest, job_root, output):
    import numpy as np
    from robots.libero.v5_fixture_parts import adjacent_panel_prompt, measured_microwave_door
    from robots.libero.v5_state import Entity
    from robots.libero.v5_verification import vertical_face

    plan = json.loads(manifest.read_text())
    if len(plan["cases"]) != 12 or any(c["kind"] != "articulate" for c in plan["cases"]):
        raise ValueError("expected twelve explicitly registered original fixture cases")
    output.mkdir(parents=True, exist_ok=False)
    checked, errors, rows, artifact_manifests, geometry = {}, [], [], [], []

    def check(path, expected=None):
        path = Path(path)
        key = str(path)
        if key not in checked:
            checked[key] = {"sha256": sha(path), "reference_sha256": expected}
        if expected is not None and checked[key]["sha256"] != expected:
            errors.append({"path": key, "reason": "reference_hash_mismatch"})
        return path

    check(plan["base_config"]["path"], plan["base_config"]["sha256"])
    source_ids = []
    for shard in range(3):
        source_path = job_root / f"source_identity_part{shard}.json"
        identity = json.loads(check(source_path).read_text())
        if identity["manifest_sha256"] != sha(manifest):
            errors.append({"shard": shard, "reason": "producer_manifest_mismatch"})
        for name, digest in identity["files"].items():
            check(Path(identity["source"]) / name, digest)
        source_ids.append(identity)
        ledger = job_root / f"part{shard}" / "episodes.jsonl"
        trials = [json.loads(line) for line in check(ledger).read_text().splitlines() if line.strip()]
        if [r["case"] for r in trials] != plan["cases"][shard::3]:
            errors.append({"shard": shard, "reason": "case_coverage_or_order_changed"})
        for row in trials:
            root = Path(row["output_dir"])
            check(root / "choices.jsonl", row["choices_sha256"])
            state_manifest = root / "states.json"
            recorded = json.loads(check(state_manifest).read_text())
            stage_summaries = []
            stages = [*row.get("setup", []), *([row["first_attempt"]] if row.get("first_attempt") else [])]
            for stage in stages:
                before, after = stage.get("private_before", {}), stage.get("private_after", {})
                receipt = stage.get("receipt", {})
                endpoint = stage.get("verification_measurements", {}).get("articulation", {})
                clouds = []
                for phase in ("before", "after"):
                    for kind in ("frame", "moving"):
                        face = (endpoint.get(phase) or {}).get(kind)
                        if face and face.get("path"):
                            check(face["path"], face["sha256"])
                            clouds.append({"phase": phase, "kind": kind, "path": face["path"],
                                           "sha256": face["sha256"], "points": face["points"],
                                           "normal_xy": face["normal_xy"], "centre": face["centre"]})
                stage_summaries.append({"phase": stage["phase"], "selected": stage["selected"],
                    "requested_predicate": before.get("predicate"),
                    "truth_before": before.get("satisfied"), "truth_after": after.get("satisfied"),
                    "qpos_before": first_qpos(before), "qpos_after": first_qpos(after),
                    "transition": transition(before.get("satisfied"), after.get("satisfied")),
                    "executed_controls": stage.get("executed_actions"),
                    "chunk_action_counts": dict(Counter(f"{m.get('requested_action_count')}->{m.get('executed_action_count')}"
                        for m in stage.get("motion_evidence", []) if m.get("name") == "vla_act_chunk")),
                    "receipt_verification": receipt.get("verification"),
                    "public_verified": receipt.get("articulate_verified"),
                    "public_reason": endpoint.get("reason", receipt.get("reason")),
                    "endpoint_before": endpoint.get("before"), "endpoint_after": endpoint.get("after"),
                    "independent_endpoint_clouds": clouds})
            rows.append({"case": row["case"], "status": row["status"], "output_dir": str(root),
                         "stages": stage_summaries, "new_training_rows": row["new_training_rows"]})
            # Enumerate only each trial's explicit producer manifest, not a directory scan.
            for step in recorded["steps"]:
                index = step["step_idx"]
                files = {name: root / name / f"{index:02d}{Path(name).suffix}" for name in step["artifacts"]}
                for path in files.values():
                    check(path)
                artifact_manifests.append({"case": row["case"]["name"], "step": index,
                                           "manifest": str(state_manifest), "files": list(map(str, files.values()))})
                entities = next((s.get("public_before", {}).get("entities", []) for s in stages
                                 if any(e.get("source_step") == index for e in s.get("public_before", {}).get("entities", []))), [])
                for name, path in files.items():
                    match = re.fullmatch(r"fixture_points_(e\d+)_(agentview|wrist)_([a-f0-9]+)\.npz", name)
                    if not match:
                        continue
                    parent_record = next((e for e in entities if e["id"] == match[1] and e["name"] == "microwave"), None)
                    if parent_record is None:
                        continue
                    parent = Entity(**{k: parent_record[k] for k in ("id", "name", "xyz", "lower", "upper", "visible", "source_step", "part_of", "geometry")})
                    with np.load(path) as data:
                        cloud = data[data.files[0]]
                    door, evidence = measured_microwave_door(parent, cloud)
                    sample = {"case": row["case"]["name"], "step": index, "camera": match[2],
                        "parent_cloud": {"path": str(path), "sha256": sha(path)},
                        "points": len(cloud), "parent_shell_is_independent_door": door is not None,
                        "whole_shell_door_fit": evidence, "whole_shell_vertical_plane": vertical_face(cloud)}
                    world_name = f"{match[2]}_world_high.npz"
                    if world_name in files:
                        with np.load(files[world_name]) as data:
                            world = data[data.files[0]]
                        point, proposal = adjacent_panel_prompt(world, parent)
                        sample.update(adjacent_panel_point=point, adjacent_panel_geometry=proposal)
                    geometry.append(sample)
    counts = Counter(s["transition"] for row in rows for s in row["stages"] if s["phase"] == "first_attempt")
    report = {"manifest": {"path": str(manifest), "sha256": sha(manifest)},
        "job": 3655, "cases": len(rows), "first_attempt_transitions": dict(counts),
        "public_verified": sum(s["public_verified"] is True for row in rows for s in row["stages"] if s["phase"] == "first_attempt"),
        "public_false": sum(s["public_verified"] is False for row in rows for s in row["stages"] if s["phase"] == "first_attempt"),
        "public_unknown": sum(s["public_verified"] is None for row in rows for s in row["stages"] if s["phase"] == "first_attempt"),
        "setup_endpoint_destroyed": sum(s["transition"] == "already_satisfied_destroyed" for row in rows for s in row["stages"] if s["phase"] == "setup"),
        "source_identities": source_ids, "artifact_files_hashed": len(checked),
        "reference_hash_failures": errors, "new_training_rows": 0, "qualification_authorized": False,
        "same_truth_and_measured_roles": "private predicates/qpos are diagnostic labels only; proposal is public RGB-D only"}
    for name, value in (("report.json", report), ("cases.json", rows), ("public_geometry.json", geometry),
                        ("artifact_sha_audit.json", checked), ("explicit_state_manifests.json", artifact_manifests)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "source_identities"}, indent=2))
    if errors:
        raise SystemExit("fixture reference integrity mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.manifest, args.job_root, args.output)


if __name__ == "__main__":
    main()
