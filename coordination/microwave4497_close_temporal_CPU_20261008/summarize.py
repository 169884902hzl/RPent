"""Align action-end labels and publicly captured door planes by executed block."""

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def private_label(label):
    """Use only the already saved diagnostic label, never a control decision."""
    label = label or {}
    qpos = label.get("joint_qpos")
    return {"source": label.get("source"), "satisfied": label.get("satisfied"),
            "joint_qpos": qpos, "sim_time": label.get("sim_time"), "predicate": label.get("predicate")}


def angle(frame):
    fixed, moving = frame.get("frame"), frame.get("moving")
    if not fixed or not moving:
        return None
    a, b = fixed["normal_xy"], moving["normal_xy"]
    norm = math.sqrt(sum(v * v for v in a) * sum(v * v for v in b))
    if not norm:
        return None
    dot = abs(sum(x * y for x, y in zip(a, b))) / norm
    return math.degrees(math.acos(max(0., min(1., dot))))


def summarize(data):
    frames, cycles, before = [], [], []
    labels = defaultdict(list)
    for score in data["private_scores"]:
        # after_actual_chunk is zero-based and recorded before increment;
        # release/move/public callback scores use completed-block count.
        block = score["chunk"] + (score["phase"] == "after_actual_chunk")
        labels[block].append({"phase": score["phase"], **private_label(score.get("label"))})
    for record in data["public_records"]:
        public = record.get("measurement") or {}
        samples = []
        for index, frame in enumerate(record["frames"]):
            row = {"phase": record["phase"], "block": record.get("chunks"), "frame_index": index,
                "source_step": frame.get("source_step"), "source_cameras": frame.get("source_cameras"),
                "fixed_available": bool(frame.get("frame")), "door_available": bool(frame.get("moving")),
                "relative_angle_deg": angle(frame), "arm_withdrawn": frame.get("arm_withdrawn"),
                "occluded": frame.get("occluded"), "interval_controls": frame.get("interval_controls"),
                "per_camera": {camera: {"fixed_available": bool(view.get("frame")),
                    "door_available": bool(view.get("moving")), "measurement_counts": view.get("measurement_counts"),
                    "robot_mask_evidence": frame.get("robot_mask_evidence", {}).get(camera)}
                    for camera, view in frame.get("views", {}).items()}}
            samples.append(row)
            frames.append(row)
        withdrawal = record["frames"][0].get("withdrawal") or {}
        verdict = {key: public.get(key) for key in ("status", "reason", "endpoint_reached", "stop_admitted",
                                                   "requested_direction_observed", "rejected_observation")}
        if record["phase"] == "before":
            before.append({"baseline_attempt": record.get("baseline_attempt"), "frames": samples,
                           "verdict": verdict, "withdrawal": withdrawal})
            continue
        block = record["chunks"]
        scores = labels[block]
        action_end = next((label for label in scores if label["phase"] == "after_actual_chunk"), None)
        release_labels = [label for label in scores if label["phase"] == "after_fixture_release"]
        callback_labels = [label for label in scores if label["phase"] == "after_public_stop_before_recovery"]
        lost_after_release = bool(action_end and action_end["satisfied"] is True
                                  and any(label["satisfied"] is False for label in release_labels))
        lost_after_callback = bool(action_end and action_end["satisfied"] is True
                                   and callback_labels and callback_labels[-1]["satisfied"] is False)
        cycles.append({"block": block, "action_end_private": action_end, "private_labels": scores,
            "withdrawal": withdrawal, "withdrawal_released": "release" in withdrawal,
            "withdrawal_moves": len(withdrawal.get("moves", [])), "public_frames": samples,
            "public_verdict": verdict, "closed_then_not_closed_after_release": lost_after_release,
            "closed_then_not_closed_after_callback": lost_after_callback})
    summary = {"temporal_records": len(data["public_records"]), "baseline_pairs": len(before),
        "after_pairs": len(cycles), "fresh_public_frames": len(frames),
        "fixed_plane_frames": sum(row["fixed_available"] for row in frames),
        "door_plane_frames": sum(row["door_available"] for row in frames),
        "both_plane_frames": sum(row["fixed_available"] and row["door_available"] for row in frames),
        "source_camera_counts": dict(Counter(camera for row in frames for camera in (row["source_cameras"] or []))),
        "occlusion_counts": dict(Counter(str(row["occluded"]) for row in frames)),
        "after_verdict_counts": dict(Counter(str(cycle["public_verdict"]["status"]) for cycle in cycles)),
        "after_reason_counts": dict(Counter(str(cycle["public_verdict"]["reason"]) for cycle in cycles)),
        "public_endpoints": sum(cycle["public_verdict"]["endpoint_reached"] is True for cycle in cycles),
        "public_stops": sum(cycle["public_verdict"]["stop_admitted"] is True for cycle in cycles),
        "withdrawal_release_calls_in_after_pairs": sum(cycle["withdrawal_released"] for cycle in cycles),
        "withdrawal_move_calls_in_after_pairs": sum(cycle["withdrawal_moves"] for cycle in cycles),
        "action_end_true_close_labels": sum(bool(cycle["action_end_private"])
                                            and cycle["action_end_private"]["satisfied"] is True for cycle in cycles),
        "action_end_close_label_count": sum(cycle["action_end_private"] is not None for cycle in cycles),
        "closed_then_not_closed_after_release": sum(cycle["closed_then_not_closed_after_release"] for cycle in cycles),
        "closed_then_not_closed_after_callback": sum(cycle["closed_then_not_closed_after_callback"] for cycle in cycles)}
    return {"version": "microwave4497-close-temporal-diagnosis/1-dev", "job": data["job"],
        "status": data["status"], "sacct": data["sacct"], "manifest": data["manifest"], "source_snapshot": data["source_snapshot"],
        "case": data["case"], "wall_s": data["wall_s"], "server_chunk_execution": data["server_chunk_execution"],
        "receipt": data["receipt"], "contract": data["contract"], "physical_actions": data["physical_actions"],
        "executed_vla_actions": data["executed_vla_actions"], "private_before": private_label(data["private_before"]),
        "private_after": private_label(data["private_after"]), "summary": summary, "baseline": before,
        "cycles": cycles, "private_baseline_labels": labels[0], "all_private_labels": data["private_scores"],
        "training_allowed": False, "qualification": False,
        "interpretation_limits": ["Single previously visited original state: method development, not confirmation.",
            "Repeated frames and blocks are correlated; availability counts are not independent success trials.",
            "Private joint/predicate labels are post-execution measurements only and do not select commands or stops.",
            "after_public_stop_before_recovery is a legacy scoring phase name; a truthy evidence dict is not an admitted stop.",
            "Final placement or joint success is not implied by a publicly measured plane or a completed startup contract."],
        "inputs": data["inputs"]}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    source = root / "records.json"
    result = summarize(json.loads(source.read_text()))
    path = root / "diagnosis.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, indent=2) + "\n")
    manifest = {"version": "microwave4497-diagnostic-manifest/1", "job": 4497, "training_allowed": False,
        "qualification": False, "files": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in (source, path, Path(__file__), root / "collect.py")], "remote_inputs": result["inputs"]}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"private_after": result["private_after"], "receipt": result["receipt"], "summary": result["summary"]}))
