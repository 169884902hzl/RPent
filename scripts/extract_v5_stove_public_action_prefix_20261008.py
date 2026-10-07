"""Pin saved public on/off actions for possible train-state CPU replay."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--episode-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.episode)["sha256"] != args.episode_sha256:
        raise ValueError("Explicit episode changed")
    record = json.loads(args.episode.read_text())
    case = record["case"]
    if (case["episode"]["suite"] != "libero_goal" or case["episode"]["task"] != 7
            or case["episode"]["seed"] not in (0, 1, 2)
            or record["status"] != "fixed_public_control_sequence_recorded"):
        raise ValueError("Only three previously visited train states may be replayed")
    actions, checkpoints, phases = [], [], []
    for phase in ("on_setup", "off_contact"):
        evidence = record[phase]["motion_evidence"]
        chunks = 160 if phase == "on_setup" else record["fixed_off_chunks"]
        if len(evidence) != chunks or record[phase]["executed_control_actions"] != chunks * 5:
            raise ValueError("Missing public controls; do not fill gaps")
        start = len(actions)
        for index, row in enumerate(evidence):
            raw = np.asarray(row["actions"], dtype=np.float64)
            encoded = np.asarray(raw, dtype="<f4", order="C")
            if (row["name"] != "vla_act_chunk" or raw.shape != (5, 7)
                    or row["executed_action_count"] != 5 or row["steps_used"] != 5
                    or not np.isfinite(raw).all()
                    or not np.array_equal(raw, encoded.astype(np.float64))):
                raise ValueError("Saved numeric actions do not restore losslessly as float32")
            actions.extend(encoded.tolist())
            checkpoints.append({"phase": phase, "chunk": index + 1,
                "controls": len(actions), "final_eef_pos": row["final_eef_pos"],
                "gripper_opening": row["gripper_opening"],
                "action_chunk_sha256": hashlib.sha256(encoded.tobytes()).hexdigest()})
        phases.append({"phase": phase, "first_control": start, "controls": chunks * 5})
    encoded = np.asarray(actions, dtype="<f4", order="C")
    args.output.mkdir(parents=True, exist_ok=False)
    action_path = args.output / "public_prefix_actions.npy"
    np.save(action_path, encoded, allow_pickle=False)
    restored = np.load(action_path, allow_pickle=False)
    if restored.tobytes() != encoded.tobytes():
        raise ValueError("Saved action bytes failed exact roundtrip")
    checkpoint_path = args.output / "public_chunk_checkpoints.json"
    checkpoint_path.write_text(json.dumps(checkpoints, indent=2) + "\n")
    report = {"schema": "stove-public-action-prefix-replay-packet/1",
        "episode": identity(args.episode), "producer": identity(Path(__file__)),
        "original_episode": case["episode"], "original_raw_state_sha256": case["state_sha256"],
        "original_bddl": case["bddl"], "original_init_file": case["init_file"],
        "actions": identity(action_path), "checkpoints": identity(checkpoint_path),
        "action_encoding": "C contiguous little-endian float32",
        "action_bytes_sha256": hashlib.sha256(encoded.tobytes()).hexdigest(),
        "phases": phases, "controls": len(encoded),
        "all_saved_actions_exactly_representable_as_float32": True,
        "npy_roundtrip_bytes_identical": True,
        "scope": "before_setup through fixed off endpoint; withdrawal excluded",
        "reset_prelude": "must execute the same pinned environment reset and verify public chunk checkpoints; no guessed controls",
        "physical_replay_verified": False,
        "same_action_prefix_causal_comparison_admitted": False,
        "private_labels_read": False, "private_labels_control_execution": False,
        "validation_episodes_read": False, "training_allowed": False,
        "state_role": "previously visited original verifier-train state, diagnostic reuse only"}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": identity(args.output / "manifest.json"),
        "controls": len(encoded), "action_bytes_sha256": report["action_bytes_sha256"],
        "physical_replay_verified": False}, indent=2))


if __name__ == "__main__":
    main()
