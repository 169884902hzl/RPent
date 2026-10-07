"""Replay pinned public controls on previously visited original stove train states.

The two fixed suffixes run only after every saved public checkpoint matches.
No image renderer, policy, SAM, validation state or private stopping signal is used.
"""

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import time


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(reference):
    if not Path(reference["path"]).is_absolute() or identity(reference["path"]) != reference:
        raise ValueError("Explicit input changed: " + reference["path"])
    return Path(reference["path"])


def module_at(name, reference):
    source = pinned(reference)
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--reset-adapter", type=Path, required=True)
    parser.add_argument("--reset-adapter-sha256", required=True)
    parser.add_argument("--sdk-source", type=Path, required=True)
    parser.add_argument("--sdk-source-sha256", required=True)
    parser.add_argument("--label-source", type=Path, required=True)
    parser.add_argument("--label-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suffix-comparison", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard" or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        parser.error("Require LIBERO_TYPE=standard and CUDA_VISIBLE_DEVICES=''")
    packet_ref = {"path": str(args.packet.resolve()), "sha256": args.packet_sha256}
    packet = json.loads(pinned(packet_ref).read_text())
    episode = packet["original_episode"]
    if (episode["suite"] != "libero_goal" or episode["task"] != 7
            or episode["seed"] not in (0, 1, 2) or packet["training_allowed"]):
        raise ValueError("Only previously visited original train diagnostic states are allowed")
    refs = {
        "reset_adapter": {"path": str(args.reset_adapter.resolve()), "sha256": args.reset_adapter_sha256},
        "sdk_source": {"path": str(args.sdk_source.resolve()), "sha256": args.sdk_source_sha256},
        "private_postexecution_labels": {"path": str(args.label_source.resolve()), "sha256": args.label_source_sha256},
    }
    for ref in refs.values():
        pinned(ref)
    # The SDK source fixes the reset prelude. No missing actions are guessed.
    sdk = pinned(refs["sdk_source"]).read_text()
    if "for _ in range(15):" not in sdk or "zero_actions[:, -1] = -1" not in sdk:
        raise ValueError("Pinned SDK no longer contains the declared reset prelude")
    import numpy as np
    import torch
    from libero.libero.envs.env_wrapper import ControlEnv
    reset = module_at("stove_saved_prefix_reset", refs["reset_adapter"])
    actions = np.load(pinned(packet["actions"]), allow_pickle=False)
    checkpoints = json.loads(pinned(packet["checkpoints"]).read_text())
    if (actions.dtype != np.dtype("<f4") or actions.shape != (packet["controls"], 7)
            or hashlib.sha256(actions.tobytes()).hexdigest() != packet["action_bytes_sha256"]
            or not np.isfinite(actions).all() or len(checkpoints) * 5 != len(actions)):
        raise ValueError("Saved public action packet is incomplete")
    bddl = pinned(packet["original_bddl"])
    states = torch.load(pinned(packet["original_init_file"]), map_location="cpu", weights_only=False)
    state = np.asarray(states[episode["seed"]], dtype="<f8", order="C")
    if hashlib.sha256(state.tobytes()).hexdigest() != packet["original_raw_state_sha256"]:
        raise ValueError("Original raw state identity changed")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "stove-saved-public-prefix-CPU-replay/1", "packet": packet_ref,
        "source_files": {"producer": identity(__file__), "ControlEnv": identity(inspect.getfile(ControlEnv)), **refs},
        "original_episode": episode, "original_raw_state_sha256": packet["original_raw_state_sha256"],
        "public_reset_controls": 15, "reset_action": [0, 0, 0, 0, 0, 0, -1],
        "prefix_controls": len(actions), "suffix_controls_each": 20 if args.suffix_comparison else 0,
        "saved_prefix_action_bytes_sha256": packet["action_bytes_sha256"],
        "physics_executed": False, "physical_prefix_verified": False,
        "suffix_comparison_executed": False, "private_labels_control_execution": False,
        "private_labels_read_after_fixed_execution_only": True, "training_allowed": False,
        "validation_episodes_read": False, "PRO_perturbation_files_read": False,
        "renderer_or_GPU_or_policy_used": False,
        "state_role": "previously visited original verifier-train state; CPU physical diagnostic only",
        "replays": [], "status": "running",
    }
    report_path = args.output / "manifest.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    def observation(raw):
        eef = np.asarray(raw["robot0_eef_pos"], dtype=np.float32)
        grip = np.asarray(raw["robot0_gripper_qpos"], dtype=np.float32)
        return eef, float(abs(grip[0]) + abs(grip[1]))

    def new_wrapper():
        wrapper = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=False,
            has_renderer=False, has_offscreen_renderer=False, camera_names=[],
            ignore_done=True, horizon=10015)
        reset.attach_reset_seed(wrapper)
        wrapper.seed(episode["seed"])
        wrapper.reset()
        wrapper.set_init_state(state)
        settling = np.zeros(7)
        settling[-1] = -1
        for _ in range(15):
            wrapper.step(settling)
        return wrapper

    save()
    wrappers = []
    try:
        conditions = ("release", "neutral_no_release") if args.suffix_comparison else ("prefix_only",)
        for condition in conditions:
            started = time.perf_counter()
            wrapper = new_wrapper()
            wrappers.append(wrapper)
            result = {"condition": condition, "checkpoints": [], "prefix_verified": False,
                "prefix_controls_executed": 0, "suffix_controls_executed": 0}
            report["replays"].append(result)
            for index, expected in enumerate(checkpoints):
                chunk = actions[index * 5:(index + 1) * 5]
                chunk_sha = hashlib.sha256(chunk.tobytes()).hexdigest()
                if chunk_sha != expected["action_chunk_sha256"]:
                    raise ValueError("Chunk bytes differ before physical execution")
                for action in chunk:
                    raw, _, _, _ = wrapper.step(action)
                    result["prefix_controls_executed"] += 1
                    report["physics_executed"] = True
                eef, gripper = observation(raw)
                wanted_eef = np.asarray(expected["final_eef_pos"], dtype=np.float32)
                match = bool(np.array_equal(eef, wanted_eef) and gripper == expected["gripper_opening"])
                row = {"controls": result["prefix_controls_executed"], "phase": expected["phase"],
                    "chunk": expected["chunk"], "action_chunk_sha256": chunk_sha,
                    "eef_xyz": eef.tolist(), "expected_eef_xyz": wanted_eef.tolist(),
                    "eef_max_abs_error_m": float(np.max(np.abs(eef - wanted_eef))),
                    "gripper_opening": gripper, "expected_gripper_opening": expected["gripper_opening"],
                    "gripper_abs_error_m": abs(gripper - expected["gripper_opening"]), "exact_public_match": match}
                result["checkpoints"].append(row)
                if not match:
                    save()
                    raise ValueError("Public prefix mismatch at control " + str(row["controls"]))
            result["prefix_verified"] = True
            report["physical_prefix_verified"] = True
            if args.suffix_comparison:
                suffix = np.zeros(7, dtype=np.float32)
                suffix[-1] = -1 if condition == "release" else 0
                result["suffix_action"] = suffix.tolist()
                result["suffix_public_observations"] = []
                for index in range(20):
                    raw, _, _, _ = wrapper.step(suffix)
                    eef, gripper = observation(raw)
                    result["suffix_controls_executed"] += 1
                    result["suffix_public_observations"].append({"control": index + 1,
                        "eef_xyz": eef.tolist(), "gripper_opening": gripper})
            result["wallclock_s"] = time.perf_counter() - started
            save()
        # Private labels are read only after all predetermined physics is done.
        labels = module_at("stove_saved_prefix_postexecution", refs["private_postexecution_labels"])
        private = []
        for result, wrapper in zip(report["replays"], wrappers, strict=True):
            private.append({"condition": result["condition"], "controller_access": False,
                "label": labels.private_skill_truth(wrapper, {"kind": "articulate", "mode": "turn_off",
                    "object_symbol": "flat_stove_1"})})
        private_path = args.output / "private_postexecution_labels.json"
        private_path.write_text(json.dumps(private, indent=2) + "\n")
        report["private_postexecution_labels"] = identity(private_path)
        report["suffix_comparison_executed"] = args.suffix_comparison
        report["status"] = "completed"
        save()
        print(json.dumps({"manifest": identity(report_path), "physical_prefix_verified": True,
            "suffix_comparison_executed": args.suffix_comparison}, indent=2))
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        save()
        raise
    finally:
        for wrapper in wrappers:
            wrapper.close()


if __name__ == "__main__":
    main()
