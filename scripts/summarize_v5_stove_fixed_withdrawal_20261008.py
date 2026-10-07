"""Summarize same-run public withdrawal frames before reading private labels."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(ref):
    if not Path(ref["path"]).is_absolute() or identity(ref["path"]) != ref:
        raise ValueError("Explicit input changed: " + ref["path"])
    return Path(ref["path"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--episode-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.episode)["sha256"] != args.episode_sha256:
        raise ValueError("Explicit physical episode changed")
    episode = json.loads(args.episode.read_text())
    if (episode["status"] != "fixed_public_control_sequence_recorded"
            or episode["case"]["episode"]["suite"] != "libero_goal"
            or episode["case"]["episode"]["task"] != 7
            or episode["case"]["episode"]["seed"] not in (0, 1, 2)
            or episode["fixed_off_chunks"] not in (20, 40, 160)):
        raise ValueError("Only completed fixed withdrawal train diagnostics are allowed")
    args.output.mkdir(parents=True, exist_ok=False)
    public = []
    private_refs = []
    before = episode["captures"]["after_contact"]
    current = json.loads(pinned(before["public_measurements"]).read_text())
    public.append({"phase": "after_contact", "index": 0,
        "public_measurements": before["public_measurements"],
        "source_step": before["source_step"], "views": current["views"],
        "public_robot_observation": episode["release_only"]["robot_before"],
        "hold_controls_since_previous_frame": 0})
    private_refs.append(before["labels"])
    for phase in ("after_release", "after_retreat"):
        seq_ref = episode["public_sequences"][phase]["public_sequence"]
        seq = json.loads(pinned(seq_ref).read_text())
        for i, frame in enumerate(seq["frames"]):
            public.append({"phase": phase, "index": i, "sequence": seq_ref, **frame})
        # Retain references only. Their label files are opened after the public
        # montage and public records have both been fully written.
        private_refs.append(episode["public_sequences"][phase]["private_sequence_labels"])
    montage = Image.new("RGB", (1024, 448 * len(public)), "#eeeeee")
    draw = ImageDraw.Draw(montage)
    for ri, frame in enumerate(public):
        for ci, camera in enumerate(("agentview", "wrist")):
            rgb = frame["views"][camera]["files"]["rgb"]
            image = Image.open(pinned(rgb)).convert("RGB")
            image.thumbnail((500, 404))
            montage.paste(image, (ci * 512 + 6, ri * 448 + 38))
            draw.text((ci * 512 + 6, ri * 448 + 10),
                f"{frame['phase']} {frame['index']} {camera}; step {frame['source_step']}", fill="black")
    montage_path = args.output / "public_withdrawal_sequence.png"
    montage.save(montage_path)
    public_path = args.output / "public_records.json"
    public_path.write_text(json.dumps({"frames": public, "private_labels_read": False,
        "fixed_off_chunks": episode["fixed_off_chunks"],
        "withdrawal_intervention": {key: value for key, value in episode["withdrawal_intervention"].items()
            if key not in ("before", "after_release", "after_retreat")}}, indent=2) + "\n")

    # Labels are postexecution diagnosis only and do not update public inputs.
    label_refs = [private_refs[0]]
    for ref in private_refs[1:]:
        label_refs.extend(json.loads(pinned(ref).read_text())["labels"])
    private = []
    for frame, ref in zip(public, label_refs, strict=True):
        labels = json.loads(pinned(ref).read_text())
        result = labels["requested_predicates"]["turn_off"]
        if labels["source_step"] != frame["source_step"]:
            raise ValueError("Public and private frame references do not pair")
        private.append({"phase": frame["phase"], "index": frame["index"],
            "source_step": frame["source_step"], "private_reference": ref,
            "turn_off_satisfied": result["satisfied"], "joint_qpos": result["joint_qpos"],
            "joint_names": result["joint_names"], "sim_time": result["sim_time"],
            "controller_access": False, "affects_actions_or_stop": False})
    private_path = args.output / "private_postexecution_change_diagnosis.json"
    private_path.write_text(json.dumps({"records": private,
        "controller_access": False, "affects_actions_or_stop": False,
        "threshold_fitting": False}, indent=2) + "\n")
    report = {"schema": "stove-fixed-withdrawal-same-run-summary/1", "episode": identity(args.episode),
        "producer": identity(Path(__file__)), "public_records": identity(public_path),
        "public_montage": identity(montage_path), "private_postexecution_diagnosis": identity(private_path),
        "public_frames": len(public), "view_count": 2 * len(public),
        "paired_observation_within_same_run": True,
        "old_r4_action_prefix_replay_verified": False,
        "measurement_insertion_is_physical_intervention": True,
        "private_labels_control_execution": False, "stop_admitted": False,
        "validation_episodes_read": False,
        "release_controls": episode["withdrawal_intervention"]["release_controls"],
        "retreat_controls": episode["withdrawal_intervention"]["retreat_controls"],
        "hold_controls": 24}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
