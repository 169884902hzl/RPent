"""Audit named original pan/moka ledgers for wide-aperture calibration evidence.

Artifact reads follow explicit episode output directories and states.json
declarations. No glob/scandir, simulator run, policy call or verdict changes.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {"path": str(path), "sha256": sha(path)}


def artifact(output, name, step):
    if Path(name).name != name:
        raise ValueError("state manifest artifact is not a base name")
    return output / name / f"{step:02d}{Path(name).suffix}"


def calibration_design():
    return {
        "qualification": False,
        "threshold_fitting_on_confirmation": False,
        "scope": "original40/90 single-grasp diagnostic calibration only; no PRO or training task additions",
        "minimum_development_pilot": {
            "per_class": {"wide_aperture_true_positive_episodes": 30, "true_negative_episodes": 30},
            "classes": ["frypan", "moka pot"],
            "unique_scene_units": "distinct task/init tuples, grouped across conditions and repeats; register exclusion of all confirmation states before sampling",
            "purpose": "pilot estimates point-count separability; 30/30 is not independent 95-percent verifier qualification",
        },
        "true_positive": "held above measured support after 5cm trial lift; synchronized private collision clearance/finger support confirms held at both public frames and throughout 0.5s; includes naturally wide handle/rim grasps",
        "true_negative_strata": [
            "empty open fingers near but not holding a visible target",
            "target remains on support while gripper closes near it",
            "target is near one finger only or falls after an initial lift",
            "gripper/furniture/nearby-object points visible near fingers but not target-mask points",
        ],
        "negative_balance": "register ten of each first three strata per class; include fourth contamination stratum within those episodes; do not recategorize from visual score",
        "measurements_to_save_each_frame": [
            "immutable source RGB/depth/world point cloud and exact SAM instance mask per agentview/wrist, file SHA and camera metadata",
            "camera-only object point arrays before fusion, object_id, source_step, src=perception; missing view remains missing",
            "synchronized public eef_pos, eef_quat(body), gripper_qpos/opening from same capture, public fixed body-to-site asset SHA",
            "immutable pregrasp object geometry and measured work-surface top; never substitute object/support simulator coordinates",
            "two captures separated by recorded control duration >=0.3s plus private diagnostic contact/clearance at each capture and sustained hold",
        ],
        "measurement_only_feature": "reproduce current _opening_check exactly: points_finger=(points_world-finger_origin_world) @ R_world_site; retain points within calibrated pad depth/height half sizes, then count each closing-axis slab abs(x-side*opening/2)<=calibration513 tolerance for side=-1,+1; only target-mask points, separately per view",
        "pad_offset_diagnostic": "save both public jaw qpos and asset-derived inner-pad gap offset (-0.001m) for metrology diagnosis; current module count formula does not apply that offset, so do not silently change its finger slab definition while fitting point-count threshold",
        "fixed_geometry": "use calibration513 public MJCF rotation/pad geometry unchanged; fit point-count threshold only, never task-specific offsets or opening expansion",
        "view_policy": "do not pool fused or duplicate pixels as extra support; evaluate per-camera counts, freshness and conflict with runtime's fixed view policy",
        "locked_capture_identity": "freeze camera resolution, point dtype, SAM checkpoint/config and runtime selector; record timestamp or simulator-time/capture id and forbid intervening actions between public frame and private diagnostic snapshot",
        "fit_rule": "candidate integer thresholds from observed per-finger counts; reject absent/ambiguous object association as unknown, not negative; use development-only grouped splits to compare FP/FN and coverage; if TP/TN counts overlap, repair measurement or keep unknown rather than pick a permissive threshold",
        "validation": "freeze threshold/config/SHA before collecting separate new original holdout; report TP/TN/FP/FN/unknown, unconditional coverage and agreement, FPR=FP/Nnegative and FNR=FN/Npositive with Wilson intervals; unknown is not counted as correct",
        "existing_gate_unchanged": "final independent class confirmation >=100 new states/class; overall truth grasp>=95%, each class>=90%, public verifier agreement>=95%; calibration pilot cannot satisfy or lower these gates",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--pan-manifest", type=Path, required=True)
    parser.add_argument("--moka-manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--runtime-source", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text())
    plans = [json.loads(path.read_text()) for path in (args.pan_manifest, args.moka_manifest)]
    registered = {c["name"]: c for p in plans for c in p["cases"]}
    if len(registered) != 700:
        raise ValueError("requires exactly explicit original pan400+moka300 registration")
    opening = calibration["opening_calibration"]
    wide_min = opening["open_empty_min_m"] - opening["tolerance_m"]
    sources, records, totals = [], [], Counter()
    seen = set()
    by_condition = {}
    for ledger in args.ledger:
        data = ledger.read_bytes()
        rows = [json.loads(line) for line in data.splitlines() if line]
        sources.append({"path": str(ledger), "sha256": hashlib.sha256(data).hexdigest(), "rows": len(rows)})
        for row in rows:
            case = row["case"]
            name = case["name"]
            if name not in registered or name in seen or case != registered[name]:
                raise ValueError("episode registration mismatch or duplicate")
            if case["episode"]["suite"] not in {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}:
                raise ValueError("only original task evidence permitted")
            seen.add(name)
            totals["episodes"] += 1
            counter = by_condition.setdefault(case["condition"], Counter())
            counter["episodes"] += 1
            output = Path(row["output_dir"])
            choices = output / "choices.jsonl"
            if sha(choices) != row["choices_sha256"]:
                raise ValueError("closed choices evidence changed")
            config_path, state_path = output / "config.json", output / "states.json"
            config = json.loads(config_path.read_text())
            states = json.loads(state_path.read_text())
            step_index = {step["step_idx"]: step for step in states["steps"]}
            counter["record_sam_masks_enabled"] += int(config.get("record_sam_masks_v6", False))
            mask_files = []
            cloud_files, pose_steps = 0, 0
            for step in states["steps"]:
                state = step["state"]
                if all(key in state for key in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")):
                    pose_steps += 1
                for filename in step["artifacts"]:
                    if filename.startswith("v6_sam_"):
                        mask_files.append(str(artifact(output, filename, step["step_idx"])))
                    if filename in ("agentview_world_high.npz", "wrist_world_high.npz"):
                        cloud_files += int(artifact(output, filename, step["step_idx"]).is_file())
            counter["declared_target_sam_masks"] += len(mask_files)
            counter["whole_scene_cloud_files_present"] += cloud_files
            counter["robot_pose_steps"] += pose_steps
            stable = row.get("stable_visual_grasp") or {}
            frames = stable.get("frames", [])
            frame_pose_available, frame_clouds_available = 0, 0
            for frame in frames:
                after = frame.get("after") or {}
                step = step_index.get(after.get("source_step"))
                if step is not None:
                    frame_pose_available += int(all(k in step["state"] for k in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")))
                    filename = f"{frame['camera']}_world_high.npz"
                    frame_clouds_available += int(filename in step["artifacts"] and artifact(output, filename, step["step_idx"]).is_file())
            counter["verification_frames"] += len(frames)
            counter["frame_same_step_robot_pose_available"] += frame_pose_available
            counter["frame_same_step_whole_scene_cloud_available"] += frame_clouds_available
            # Old ledgers can have late private hold truth without a truth
            # sample synchronized to either public camera capture.
            synchronized_private = bool(row.get("private_phase_snapshots"))
            counter["episodes_with_synchronized_phase_truth"] += int(synchronized_private)
            points_saved = any(key in stable for key in ("measurement_clouds_by_view", "measured_points_by_view"))
            counter["episodes_with_saved_object_points_by_view"] += int(points_saved)
            final_opening = (row.get("rpent_pick_result") or {}).get("final_gripper_opening")
            wide = final_opening is not None and final_opening >= wide_min
            counter["wide_pi0_return_opening_episodes"] += int(wide)
            truth = row.get("true_sustained_grasp")
            if wide:
                counter["wide_later_hold_truth_positive"] += int(truth is True)
                counter["wide_later_hold_truth_negative"] += int(truth is False)
                counter["wide_later_hold_truth_unknown"] += int(truth is not True and truth is not False)
            records.append({"case": name, "condition": case["condition"], "episode": case["episode"],
                            "ledger": str(ledger), "choices": identity(choices), "states": identity(state_path),
                            "config": identity(config_path), "record_sam_masks_v6": config.get("record_sam_masks_v6", False),
                            "declared_sam_mask_files": mask_files, "whole_scene_cloud_files_present": cloud_files,
                            "verification_frames": len(frames), "frame_same_step_robot_pose_available": frame_pose_available,
                            "frame_same_step_whole_scene_cloud_available": frame_clouds_available,
                            "object_points_saved_by_view": points_saved, "synchronized_phase_truth_saved": synchronized_private,
                            "pi0_return_opening_m": final_opening, "wide_pi0_return_opening": wide,
                            "later_hold_truth_unchanged": truth,
                            "calibratable_minimum_points_per_finger": False})
    if seen != set(registered):
        raise ValueError("closed original full cohorts are incomplete")
    for counter in by_condition.values():
        totals.update({k: v for k, v in counter.items() if k != "episodes"})
    runtime_identity = []
    for path in args.runtime_source:
        text = path.read_text()
        runtime_identity.append({**identity(path), "has_independent_raw_view_cloud_cache": "measurement_clouds_by_view" in text,
                                 "mask_saving_exists": "record_sam_masks_v6" in text})
    report = {"scope": "all explicit closed original pan400/moka300 only; metadata/evidence audit, no recalculated verdicts",
              "script": identity(Path(__file__)), "calibration": identity(args.calibration),
              "manifests": [identity(p) for p in (args.pan_manifest, args.moka_manifest)], "ledgers": sources,
              "runtime_sources": runtime_identity, "totals": dict(totals),
              "by_condition": {k: dict(v) for k, v in by_condition.items()},
              "wide_opening_boundary_m": wide_min,
              "can_calibrate_minimum_points_per_finger": False,
              "reason": "saved complete scene clouds/robot poses do not identify exact original per-view target points; original SAM masks are absent and private final hold is later than public frames",
              "array_limit": "cloud file presence and step identity checked; no new SAM model call, per-point reconstruction or numeric threshold fitting",
              "minimum_points_per_finger_retained": None,
              "sampling_design": calibration_design(), "new_physics_trials": 0, "new_training_rows": 0,
              "runtime_changed": False, "old_verdicts_changed": False, "confirmation_eligible": False}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    records_path = args.output / "evidence_rows.jsonl"
    records_path.write_text("".join(json.dumps(record) + "\n" for record in records))
    print(json.dumps({"report": identity(path), "evidence_rows": identity(records_path),
                      "totals": dict(totals), "can_calibrate_minimum_points_per_finger": False}, indent=2))


if __name__ == "__main__":
    main()
