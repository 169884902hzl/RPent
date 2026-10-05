"""Read-only audit of explicitly registered synchronous original grasp frames.

Reads only supplied ledgers, their closed episode declarations and states.json
artifacts. Never fits thresholds, runs simulation, or substitutes a later hold
for the private instantaneous contact label. Missing evidence remains missing.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np


ORIGINAL = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    return {"path": str(path), "sha256": sha(path.read_bytes())}


def artifact(output, name, step):
    if Path(name).name != name:
        raise ValueError("artifact declaration must be a base name")
    return output / name / f"{step:02d}{Path(name).suffix}"


def array(path):
    with np.load(path, allow_pickle=False) as data:
        return data["array"]


def expected_bool(values):
    return False if any(v is False for v in values) else None if None in values else True


def audit_case(row, registered, wide_min):
    case = row["case"]
    if registered.get(case["name"]) != case or case["episode"]["suite"] not in ORIGINAL:
        raise ValueError("case is not the explicit original registration")
    output = Path(row["output_dir"])
    choices_path, states_path = output / "choices.jsonl", output / "states.json"
    choices = identity(choices_path)
    if choices["sha256"] != row["choices_sha256"]:
        raise ValueError("closed choices SHA changed")
    states = json.loads(states_path.read_text())
    steps = {s["step_idx"]: s for s in states["steps"]}
    sync = row["first_attempt"]["contact_evidence"]["private_frame_sync"]
    if (sync["version"] != "original-private-frame-sync/1" or not sync["enabled"]
            or sync["new_robot_actions"] != 0 or not sync["selection_calibration_only"]
            or sync["qualification_authorized"]):
        raise ValueError("synchronous diagnostic contract changed")
    reference = sync["pregrasp_reference"]
    errors, records = [], []
    count = Counter(episodes=1, samples=len(sync["samples"]), exact_case_match=1, choices_sha_pass=1)
    max_pose_error, max_opening_error = 0., 0.
    for index, sample in enumerate(sync["samples"]):
        step_id = sample["source_step"]
        step = steps[step_id]
        declared = set(step["artifacts"])
        def issue(message):
            errors.append({"sample": index, "source_step": step_id, "error": message})
        if sample["sample_index"] != index or sample["new_robot_actions"] != 0:
            issue("sample index or zero-action declaration mismatch")
        meta = sample["metadata"]
        meta_path = Path(meta["path"])
        if meta_path != artifact(output, f"private_frame_sync_{index:04d}.json", step_id):
            issue("sample metadata path does not match state declaration")
        if f"private_frame_sync_{index:04d}.json" not in declared:
            issue("sample metadata not declared in states")
        if sha(meta_path.read_bytes()) != meta["sha256"]:
            issue("sample metadata file SHA mismatch")
        if json.loads(meta_path.read_text()) != {k: v for k, v in sample.items() if k != "metadata"}:
            issue("sample metadata content mismatch")
        count["metadata_files_sha_content_pass"] += int(not any(e["sample"] == index for e in errors))
        before, after = sample["private_contact_before_read"], sample["private_contact"]
        if before["target"] != case["object_symbol"] or after["target"] != case["object_symbol"]:
            issue("private same-frame target differs from registered original target")
        times = (before["sim_time"], after["sim_time"], sample["sim_time"])
        time_equal = len(set(times)) == 1
        if sample["same_physics_time"] is not time_equal:
            issue("private read-time declaration mismatch")
        count["private_bracket_same_time"] += int(time_equal)
        clearance = after["lower_extent_m"] - reference["lower_extent_m"]
        touching = sorted(set(reference["other_contact_geoms"]) & set(after["other_contact_geoms"]))
        truth = bool(clearance >= .03 and after["finger_contact"] and not touching)
        if (abs(sample["private_clearance_m"] - clearance) > 1e-12
                or sample["touching_original_support_geoms"] != touching
                or sample["private_contact_clear_instant"] is not truth):
            issue("private instantaneous label recomputation mismatch")
        count["private_instant_positive" if truth else "private_instant_negative"] += 1
        public_robot, saved_robot = sample["robot_observation"], step["state"]
        pose_error = max(float(np.max(np.abs(np.asarray(public_robot[key]) - saved_robot[key])))
                         for key in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"))
        max_pose_error = max(max_pose_error, pose_error)
        count["capture_robot_pose_exact_match"] += int(pose_error == 0.)
        opening = float(public_robot["robot0_gripper_qpos"][0] - public_robot["robot0_gripper_qpos"][1])
        opening_error = abs(sample["raw_robot_gripper_opening"] - opening)
        max_opening_error = max(max_opening_error, opening_error)
        if pose_error > 1e-7:
            issue("saved capture robot pose differs from private-frame raw observation")
        frame = sample["frame"]
        view_records = {}
        for camera, view in sample["per_view"].items():
            measurement, points = view["measurement"], view["points"]
            if points is None:
                count[f"{camera}_points_missing"] += 1
                view_records[camera] = {"missing_reason": view["missing_reason"]}
                continue
            path = Path(points["path"])
            filename = f"private_frame_sync_{index:04d}_{camera}_{points['object_id']}.npz"
            if path != artifact(output, filename, step_id) or filename not in declared:
                issue(f"{camera}: target points path/declaration mismatch")
            cloud = array(path)
            point_id = identity(path)
            expected_current = (points["source_step"] == step_id
                                and points["object_id"] == measurement["id"] and points["src"] == "perception")
            if (point_id["sha256"] != points["sha256"] or sha(cloud.tobytes(order="C")) != points["point_array_sha256"]
                    or list(cloud.shape) != points["shape"] or cloud.dtype.str != points["dtype"]
                    or cloud.ndim != 2 or cloud.shape[1:] != (3,) or not np.isfinite(cloud).all()
                    or points["current"] is not expected_current
                    or measurement["source_step"] != points["source_step"] or measurement["src"] != "perception"):
                issue(f"{camera}: point payload SHA/shape/type/freshness mismatch")
            count["point_arrays"] += 1
            world_name = f"{camera}_world_high.npz"
            if world_name not in declared:
                issue(f"{camera}: whole-frame world cloud is not declared")
                continue
            world_path = artifact(output, world_name, step_id)
            world = array(world_path)
            world_id = identity(world_path)
            camera_path = artifact(output, f"{camera}_metadata.json", step_id)
            camera_meta = json.loads(camera_path.read_text())
            # The original recording has no pixel-capture sim_time; do not
            # promote equal private read times to an independently saved one.
            capture_time = camera_meta.get("sim_time", step.get("sim_time"))
            count["capture_sim_time_available"] += int(capture_time is not None)
            if capture_time is not None and capture_time != sample["sim_time"]:
                issue(f"{camera}: recorded capture sim_time differs")
            masks, exact_matches = [], []
            for filename in sorted(declared):
                if not filename.startswith(f"v6_sam_{camera}_") or not filename.endswith(".npz"):
                    continue
                mask_path = artifact(output, filename, step_id)
                mask = array(mask_path)
                raw_sha = sha(mask.tobytes(order="C"))
                if raw_sha[:16] != filename.removeprefix(f"v6_sam_{camera}_").removesuffix(".npz"):
                    issue(f"{camera}: declared SAM raw array digest mismatch")
                if mask.dtype.kind != "b" or mask.shape != world.shape[:2]:
                    issue(f"{camera}: declared SAM mask shape/type mismatch")
                    continue
                selected = world[mask].astype(np.float64)
                selected = selected[np.isfinite(selected).all(axis=1) & (np.abs(selected).sum(axis=1) > 1e-6)]
                item = {**identity(mask_path), "raw_array_sha256": raw_sha,
                        "raw_array_prefix_matches_declaration": raw_sha[:16] in filename,
                        "computed_full_file_sha_not_predeclared": True,
                        "shape": list(mask.shape), "selected_points": len(selected)}
                masks.append(item)
                if selected.shape == cloud.shape and np.array_equal(selected, cloud):
                    exact_matches.append(item["path"])
            count["declared_masks_checked"] += len(masks)
            count["target_cloud_exact_mask_matches"] += int(bool(exact_matches))
            if not exact_matches:
                issue(f"{camera}: no declared same-frame SAM mask exactly reconstructs target cloud")
            view_records[camera] = {"points": point_id, "point_array_sha256": points["point_array_sha256"],
                                    "world": world_id, "camera_metadata": identity(camera_path),
                                    "capture_sim_time": capture_time, "masks": masks,
                                    "target_cloud_exact_mask_matches": exact_matches}
        if frame is not None:
            known = set()
            for camera, value in frame["per_view"].items():
                expected = expected_bool(list(value["conditions"].values()))
                if value["verified"] is not expected:
                    issue(f"{camera}: public per-view Boolean contradiction")
                    count["boolean_contradictions"] += 1
                if value["verified"] is not None:
                    known.add(value["verified"])
            aggregate = None if len(known) != 1 else next(iter(known))
            if frame["verified"] is not aggregate:
                issue("public aggregate view Boolean contradiction")
                count["boolean_contradictions"] += 1
            public = frame["verified"]
            wide = frame["opening_m"] >= wide_min
            bucket = f"{'wide_' if wide else ''}{'pregrasp_' if sample['phase'] == 'pregrasp' else 'postgrasp_'}truth_{truth}_public_{public}"
            count[bucket] += 1
            count["wide_frames"] += int(wide)
        records.append({"case": case["name"], "object_category": case["object_category"],
                        "sample_index": index, "phase": sample["phase"], "source_step": step_id,
                        "sim_time_private": sample["sim_time"], "private_bracket_same_time": time_equal,
                        "capture_robot_pose_max_abs_error": pose_error,
                        "private_instant_label": truth, "public_frame_verdict": frame["verified"] if frame else None,
                        "opening_m": opening, "wide_opening": opening >= wide_min,
                        "metadata": meta, "views": view_records})
    receipt = row["first_attempt"].get("receipt", {})
    count["execution_errors"] += int(receipt.get("verification") == "execution_error" or bool(receipt.get("error")))
    count["infrastructure_errors"] += int(row["status"] == "probe_error" or bool(row.get("raised_error")))
    return {"case": case["name"], "category": case["object_category"], "condition": case["condition"],
            "choices": choices, "states": identity(states_path), "status": row["status"],
            "counts": dict(count), "max_capture_robot_abs_error": max_pose_error,
            "max_float32_opening_abs_error_m": max_opening_error, "errors": errors}, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_id = identity(args.manifest)
    if manifest_id["sha256"] != args.manifest_sha256:
        raise ValueError("registered manifest SHA mismatch")
    manifest = json.loads(args.manifest.read_text())
    registered = {c["name"]: c for c in manifest["cases"]}
    calibration = next(iter(manifest["conditions"].values()))["overrides"]["grasp_measurement_calibration"]["opening_calibration"]
    wide_min = calibration["open_empty_min_m"] - calibration["tolerance_m"]
    totals, by_category = Counter(), defaultdict(Counter)
    sources, cases, records, seen = [], [], [], set()
    args.output.mkdir(parents=True, exist_ok=False)
    for ledger_index, ledger in enumerate(args.ledger):
        if not ledger.is_file():
            sources.append({"path": str(ledger), "missing": True, "closed_rows": 0})
            continue
        data = ledger.read_bytes()
        closed = data[:data.rfind(b"\n") + 1]
        snapshot = args.output / f"ledger{ledger_index}_closed_prefix.jsonl"
        snapshot.write_bytes(closed)
        rows = [json.loads(line) for line in closed.splitlines() if line.strip()]
        sources.append({"path": str(ledger), "read_sha256": sha(data), "read_bytes": len(data),
                        "closed_prefix": identity(snapshot), "closed_rows": len(rows), "trailing_bytes": len(data) - len(closed)})
        for row in rows:
            name = row["case"]["name"]
            if name in seen:
                raise ValueError("duplicate closed case")
            seen.add(name)
            result, frame_records = audit_case(row, registered, wide_min)
            cases.append(result)
            records.extend(frame_records)
            totals.update(result["counts"])
            by_category[result["category"]].update(result["counts"])
    evidence = args.output / "frames.jsonl"
    evidence.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records))
    unique_points, unique_masks, capture_units = set(), set(), set()
    for record in records:
        capture_units.add((record["case"], record["source_step"]))
        for view in record["views"].values():
            if "points" in view:
                unique_points.add(view["points"]["path"])
                unique_masks.update(mask["path"] for mask in view["masks"])
    report = {"version": "original-grasp-synchronized-frame-audit/1", "manifest": manifest_id,
              "qualification": False, "threshold_fitted": False, "new_training_rows": 0,
              "wide_opening_min_m": wide_min, "minimum_points_per_finger_unchanged": calibration["minimum_points_per_finger"],
              "sources": sources, "counts": dict(totals), "by_category": {k: dict(v) for k, v in by_category.items()},
              "registered_cases": len(registered), "closed_cases": len(cases), "cases": cases,
              "unique_declared_mask_paths_checked": len(unique_masks), "unique_target_point_paths_checked": len(unique_points),
              "unique_case_source_step_units": len(capture_units),
              "frame_evidence": identity(evidence),
              "limitations": ["Private labels are instantaneous contact/clearance, not sustained-hold qualification.",
                              "Saved camera metadata has no independent pixel-capture sim_time unless explicitly reported available.",
                              "Same private before/after times and same saved robot pose support alignment but do not invent missing capture timestamps.",
                              "SAM file SHA is computed; its raw-array digest prefix is independently checked from states declaration.",
                              "Repeated frames share episode/state; frame confusion counts are not independent grasp success rates.",
                              "No outcome filtering, threshold fitting, new robot action or final confirmation occurred."]}
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": identity(report_path), "counts": dict(totals), "closed_cases": len(cases),
                      "errors": [e for c in cases for e in c["errors"]]}, sort_keys=True))


if __name__ == "__main__":
    main()
