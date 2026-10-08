"""Compare fixed unloading controls after an exactly replayed public prefix."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from diagnose_hold_dynamics import BASELINE, HELPER, identity, load, module_at, pinned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard" or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        parser.error("standard LIBERO and CPU-only execution required")
    baseline = load(BASELINE)
    packet = load(baseline["packet"])
    helper = module_at("stove_unload_helper", HELPER)
    reset = helper.module_at("stove_unload_reset", baseline["source_files"]["reset_adapter"])
    import numpy as np
    import torch
    from libero.libero.envs.env_wrapper import ControlEnv

    actions = np.load(pinned(packet["actions"]), allow_pickle=False)
    checkpoints = load(packet["checkpoints"])
    states = torch.load(pinned(packet["original_init_file"]), map_location="cpu", weights_only=False)
    state = np.asarray(states[packet["original_episode"]["seed"]], dtype="<f8", order="C")
    if (actions.shape != (900, 7) or actions.dtype != np.dtype("<f4")
            or hashlib.sha256(actions.tobytes()).hexdigest() != packet["action_bytes_sha256"]
            or hashlib.sha256(state.tobytes()).hexdigest() != packet["original_raw_state_sha256"]):
        raise ValueError("pinned original state or public prefix changed")

    # Fixed controller-input directions are registered before any outcome read.
    # They use robot base axes; no object pose or joint truth chooses the action.
    release = [0, 0, 0, 0, 0, 0, -1]
    up = [0, 0, .3, 0, 0, 0, -1]
    back = [0, -.3, 0, 0, 0, 0, -1]
    diagonal = [.2, -.2, .3, 0, 0, 0, -1]
    phases = {
        "release_only": [(20, release)],
        "open_and_up": [(20, up)],
        "open_and_back": [(20, back)],
        "open_and_diagonal": [(20, diagonal)],
        "open_then_up": [(5, release), (15, up)],
        "open_then_back": [(5, release), (15, back)],
        "closed_up_then_open": [(5, [0, 0, .3, 0, 0, 0, 0]), (15, up)],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    plan_path = args.output / "registered_plan.json"
    plan = {
        "schema": "stove-fixed-public-unload-plan/1",
        "producer": identity(__file__), "baseline": BASELINE, "helper": HELPER,
        "packet": baseline["packet"], "episode": packet["original_episode"],
        "conditions": phases, "suffix_controls": 20, "settle_controls": 40,
        "control_frame": "existing controller robot-base input axes",
        "private_labels_control_actions_or_stop": False,
        "training_allowed": False, "confirmation": False,
        "purpose": "visited original development state; contact-unload diagnosis",
    }
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    report_path = args.output / "manifest.json"
    report = {"schema": "stove-fixed-public-unload-run/1", "plan": identity(plan_path),
              "status": "running", "conditions": [], "physics_executed": False}

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    save()
    try:
        for condition, sequence in phases.items():
            start = time.monotonic()
            wrapper = ControlEnv(bddl_file_name=str(pinned(packet["original_bddl"])),
                                 use_camera_obs=False, has_renderer=False,
                                 has_offscreen_renderer=False, camera_names=[],
                                 ignore_done=True, horizon=10015)
            public, private = [], []
            try:
                reset.attach_reset_seed(wrapper)
                wrapper.seed(packet["original_episode"]["seed"])
                wrapper.reset()
                wrapper.set_init_state(state)
                for _ in range(15):
                    wrapper.step(np.asarray(release, dtype=np.float32))
                exact = 0
                for index, action in enumerate(actions):
                    raw, _, _, _ = wrapper.step(action)
                    if (index + 1) % 5 == 0:
                        expected = checkpoints[(index + 1) // 5 - 1]
                        eef = np.asarray(raw["robot0_eef_pos"], dtype=np.float32)
                        grip = np.asarray(raw["robot0_gripper_qpos"], dtype=np.float32)
                        if (not np.array_equal(eef, np.asarray(expected["final_eef_pos"], dtype=np.float32))
                                or float(abs(grip[0]) + abs(grip[1])) != expected["gripper_opening"]):
                            raise ValueError("prefix mismatch at " + str(index + 1))
                        exact += 1
                initial_eef = np.asarray(raw["robot0_eef_pos"]).copy()
                for phase, segments in (("unload", sequence), ("settle", [(40, release)])):
                    for count, values in segments:
                        for _ in range(count):
                            raw, _, _, _ = wrapper.step(np.asarray(values, dtype=np.float32))
                            grip = np.asarray(raw["robot0_gripper_qpos"], dtype=np.float32)
                            public.append({"phase": phase, "control": len(public) + 1,
                                           "action": values, "eef_xyz_m": raw["robot0_eef_pos"].tolist(),
                                           "gripper_opening_m": float(abs(grip[0]) + abs(grip[1]))})
                            # Passive labels are never consulted by either loop.
                            obj = wrapper.env.fixtures_dict["flat_stove_1"]
                            joint = obj.joints[0]
                            private.append({"phase": phase, "control": len(public),
                                            "joint_qpos_rad": float(wrapper.sim.data.get_joint_qpos(joint)),
                                            "official_off": bool(wrapper.env._eval_predicate(["turnoff", "flat_stove_1"]))})
                directory = args.output / condition
                directory.mkdir()
                for name, rows in (("public_controls.jsonl", public), ("private_labels.jsonl", private)):
                    (directory / name).write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
                report["conditions"].append({
                    "condition": condition, "prefix_exact_checkpoints": exact,
                    "suffix_controls": len(public), "final_official_off": private[-1]["official_off"],
                    "off_after_unload": private[19]["official_off"],
                    "stable_off_last20": all(row["official_off"] for row in private[-20:]),
                    "eef_displacement_m": float(np.linalg.norm(np.asarray(public[-1]["eef_xyz_m"]) - initial_eef)),
                    "public_controls": identity(directory / "public_controls.jsonl"),
                    "private_labels": identity(directory / "private_labels.jsonl"),
                    "wallclock_s": time.monotonic() - start,
                })
                report["physics_executed"] = True
                save()
            finally:
                wrapper.close()
        report["status"] = "completed"
        save()
        print(json.dumps({"manifest": identity(report_path), "conditions": report["conditions"]}, indent=2))
    except Exception as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        save()
        raise


if __name__ == "__main__":
    main()
