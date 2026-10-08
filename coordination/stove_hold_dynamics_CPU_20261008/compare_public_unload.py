"""Compare fixed unloading controls after an exactly replayed public prefix."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from diagnose_hold_dynamics import BASELINE, HELPER, identity, load, module_at, pinned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-identity", type=Path)
    parser.add_argument("--runtime-identity-sha256")
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
    runtime_class, runtime_identity = None, None
    if args.runtime_identity:
        if not args.runtime_identity_sha256:
            parser.error("pinned runtime identity SHA required")
        runtime_ref = {"path": str(args.runtime_identity.resolve()), "sha256": args.runtime_identity_sha256}
        runtime_identity = load(runtime_ref)
        for reference in [*runtime_identity["files"], runtime_identity["archive"]]:
            pinned({key: reference[key] for key in ("path", "sha256")})
        sys.path.insert(0, runtime_identity["path"])
        from robots.libero.v5_runtime import V5Executor

        runtime_class = V5Executor
        phases = {"actual_runtime_open_and_lift": [(20, up), (40, release)]}
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
        "runtime_identity": runtime_identity,
        "runtime_execution": "actual clear_stove_contact method over real ControlEnv.step" if runtime_class else None,
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
                def record_step(values, phase):
                    current, _, _, _ = wrapper.step(np.asarray(values, dtype=np.float32))
                    grip = np.asarray(current["robot0_gripper_qpos"], dtype=np.float32)
                    opening = float(abs(grip[0]) + abs(grip[1]))
                    public.append({"phase": phase, "control": len(public) + 1,
                                   "action": np.asarray(values).tolist(),
                                   "eef_xyz_m": current["robot0_eef_pos"].tolist(), "gripper_opening_m": opening})
                    # Passive labels never control either loop or the runtime method.
                    obj = wrapper.env.fixtures_dict["flat_stove_1"]
                    joint = obj.joints[0]
                    private.append({"phase": phase, "control": len(public),
                                    "joint_qpos_rad": float(wrapper.sim.data.get_joint_qpos(joint)),
                                    "official_off": bool(wrapper.env._eval_predicate(["turnoff", "flat_stove_1"]))})
                    return current["robot0_eef_pos"], opening

                runtime_evidence = None
                if runtime_class:
                    # The diagnostic facade permits the original turn-on task's
                    # fixed off suffix; it does not use native success as an off signal.
                    primitive = SimpleNamespace(_last_obs_eef_pos=initial_eef,
                                                _last_obs_gripper=checkpoints[-1]["gripper_opening"],
                                                env=SimpleNamespace(terminated=False, truncated=False))

                    def runtime_step(values):
                        phase = "unload" if len(public) < 20 else "settle"
                        primitive._last_obs_eef_pos, primitive._last_obs_gripper = record_step(values, phase)

                    primitive._step_env = runtime_step
                    executor = runtime_class(SimpleNamespace(primitives=primitive), SimpleNamespace(),
                                             stove_contact_unload_v1=True)
                    runtime_evidence = executor.clear_stove_contact()
                    if runtime_evidence["executed_controls"] != 60:
                        raise ValueError("runtime suffix did not complete its declared controls")
                else:
                    for phase, segments in (("unload", sequence), ("settle", [(40, release)])):
                        for count, values in segments:
                            for _ in range(count):
                                record_step(values, phase)
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
                    "actual_runtime_evidence": runtime_evidence,
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
