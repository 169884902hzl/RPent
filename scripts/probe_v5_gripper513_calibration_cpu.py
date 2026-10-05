"""CPU original-task empty-jaw calibration, following metrology453 ControlEnv."""

import argparse
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET


def file_identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def panda_static_geometry(path):
    import numpy as np
    from scipy.spatial.transform import Rotation

    def vector(element, key, fallback):
        return np.fromstring(element.get(key, fallback), sep=" ")

    def rotation(element):
        q = vector(element, "quat", "1 0 0 0")
        return Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()

    root = ET.parse(path).getroot().find("worldbody/body")
    eef = root.find("body[@name='eef']")
    site = eef.find("site[@name='grip_site']")
    site_origin = vector(eef, "pos", "0 0 0") + rotation(eef) @ vector(site, "pos", "0 0 0")
    site_rotation = rotation(eef) @ rotation(site)
    pads = []
    for name in ("leftfinger", "rightfinger"):
        body = root.find(f"body[@name='{name}']")
        tip = body.find("body")
        pad = tip.find("geom")
        body_rotation, tip_rotation = rotation(body), rotation(tip)
        centre = (vector(body, "pos", "0 0 0") + body_rotation @
                  (vector(tip, "pos", "0 0 0") + tip_rotation @ vector(pad, "pos", "0 0 0")))
        pad_rotation = site_rotation.T @ body_rotation @ tip_rotation @ rotation(pad)
        axis = site_rotation.T @ body_rotation @ vector(body.find("joint"), "axis", "0 0 1")
        pads.append({"centre": site_rotation.T @ (centre - site_origin), "axis": axis,
                     "half_size": abs(pad_rotation) @ vector(pad, "size", "0 0 0")})
    closing = int(np.argmax(abs(pads[0]["axis"])))
    other = [i for i in range(3) if i != closing]
    offsets = [pad["centre"][closing] for pad in pads]
    return {"source": "public_robot_static_rigid_geometry", "xml": file_identity(path),
            "pose_observation": "robot0_eef_pos + robot0_eef_quat(body) times rotation_body_to_site",
            "rotation_body_to_site": (rotation(root) @ site_rotation).tolist(),
            "offset_body_to_site_m": (vector(root, "pos", "0 0 0") + rotation(root) @ site_origin).tolist(),
            "eef_pos_is_already_grip_site_position": True,
            "offset_must_not_be_added_to_eef_pos": True,
            "body_quat_is_not_site_quat": True,
            "finger_centre_offset_from_site_m": np.mean([pad["centre"] for pad in pads], axis=0).tolist(),
            "closing_axis": closing,
            "pad_depth_half_m": float(max(pad["half_size"][other[0]] for pad in pads)),
            "pad_height_half_m": float(max(pad["half_size"][other[1]] for pad in pads)),
            "joint_opening_to_inner_pad_gap_offset_m": float(abs(offsets[1] - offsets[0]) - sum(pad["half_size"][closing] for pad in pads)),
            "pad_only_does_not_cover_whole_finger_mesh": True,
            "physical_grasp_qualification": False}


def validate_robot_rigid_transform(case, geometry):
    """Check public MJCF robot frames without enabling policy observables."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    from libero.libero import get_libero_path
    from libero.libero.envs.env_wrapper import ControlEnv
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.v5_reset_seed import attach_reset_seed

    ep = case["episode"]
    if ep["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
        raise ValueError("robot-frame validation is original40-task only")
    suite = benchmark.get_benchmark(ep["suite"])()
    task = suite.get_task(ep["task"])
    bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
    env = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=False,
                     has_renderer=False, has_offscreen_renderer=False,
                     horizon=10015, ignore_done=True)
    attach_reset_seed(env)
    try:
        env.seed(ep["seed"])
        env.reset()
        env.set_init_state(suite.get_task_init_states(ep["task"])[ep["seed"]])
        obs, _, _, _ = env.step(np.zeros(7))
        # The step observation is sampled before the final integration tick.
        # Read all three robot-only sensors at the same instant for a rigid
        # transform check; mixing cached body quat with current site quat
        # creates a small false residual while the arm is settling.
        body_quat = np.asarray(env.env._observables["robot0_eef_quat"]._sensor({}))
        site_quat = np.asarray(env.env._observables["robot0_eef_quat_site"]._sensor({}))
        body_rotation = Rotation.from_quat(body_quat).as_matrix()
        site_rotation = Rotation.from_quat(site_quat).as_matrix()
        predicted_rotation = body_rotation @ np.asarray(geometry["rotation_body_to_site"])
        robot = env.robots[0]
        body_name = robot.robot_model.eef_name["right"]
        body_xyz = np.asarray(env.sim.data.get_body_xpos(body_name))
        predicted_xyz = body_xyz + body_rotation @ np.asarray(geometry["offset_body_to_site_m"])
        site_xyz = np.asarray(env.env._observables["robot0_eef_pos"]._sensor({}))
        rotation_error_rad = float(Rotation.from_matrix(predicted_rotation.T @ site_rotation).magnitude())
        position_error_m = float(np.linalg.norm(predicted_xyz - site_xyz))
        if rotation_error_rad >= 1e-6 or position_error_m >= 1e-6:
            raise ValueError(json.dumps({"rotation_error_rad": rotation_error_rad,
                                        "position_error_m": position_error_m,
                                        "eef_body_quat_xyzw": body_quat.tolist(),
                                        "eef_site_quat_xyzw": site_quat.tolist(),
                                        "rotation_body_to_site_observed": (body_rotation.T @ site_rotation).tolist(),
                                        "offset_body_to_site_observed_m": (body_rotation.T @ (site_xyz - body_xyz)).tolist()}))
        assert np.asarray(obs["robot0_proprio-state"]).size == 39, "policy proprio contract changed"
        cached_body_rotation = Rotation.from_quat(obs["robot0_eef_quat"]).as_matrix()
        cached_position_error = np.linalg.norm(np.asarray(obs["robot0_eef_pos"]) - site_xyz)
        cached_rotation_error = Rotation.from_matrix(cached_body_rotation.T @ body_rotation).magnitude()
        return {"episode": ep, "asset": file_identity(bddl),
                "eef_body_quat_xyzw": body_quat.tolist(), "eef_site_quat_xyzw_diagnostic": site_quat.tolist(),
                "robot_body_xyz_diagnostic": body_xyz.tolist(), "robot_site_xyz": site_xyz.tolist(),
                "rotation_error_rad": rotation_error_rad, "position_error_m": position_error_m,
                "cached_step_to_current_robot_sensor": {"position_difference_m": float(cached_position_error),
                                                         "rotation_difference_rad": float(cached_rotation_error)},
                "policy_proprio_dims": 39, "disabled_site_sensor_enabled": False,
                "private_object_coordinates_saved": False,
                "scope": "robot proprioception and public static gripper MJCF only"}
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enrich-existing", type=Path,
                        help="Preserve completed opening measurements and validate only robot rigid geometry")
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    import numpy as np
    from libero.libero import get_libero_path
    from libero.libero.envs.env_wrapper import ControlEnv
    from rlinf.envs.libero.utils import benchmark
    from robosuite.utils.mjcf_utils import xml_path_completion
    from robots.libero.v5_reset_seed import attach_reset_seed

    if args.enrich_existing is not None:
        report = json.loads(args.enrich_existing.read_text())
        if sorted({sample["policy_proprio_dims"] for row in report["rows"]
                   for phase in row["phases"] for sample in phase["samples"]}) != [39]:
            raise ValueError("original calibration changed policy proprio contract")
        geometry = panda_static_geometry(Path(xml_path_completion("grippers/panda_gripper.xml")))
        report["original_measurement_report"] = file_identity(args.enrich_existing)
        report["script"] = file_identity(Path(__file__))
        report["grip_site_geometry"] = geometry
        report["robot_rigid_transform_validation"] = validate_robot_rigid_transform(plan["cases"][0], geometry)
        args.output.mkdir(parents=True, exist_ok=False)
        path = args.output / "report.json"
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"report": file_identity(path), "opening_calibration": report["opening_calibration"],
                          "grip_site_geometry": geometry,
                          "robot_rigid_transform_validation": report["robot_rigid_transform_validation"]}, indent=2))
        return

    cases = {}
    for case in plan["cases"]:
        cases.setdefault(case["group"], case)
    args.output.mkdir(parents=True, exist_ok=False)
    rows, open_tails, closed_tails = [], [], []
    for group, case in cases.items():
        ep = case["episode"]
        if ep["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("opening calibration is original40-task only")
        suite = benchmark.get_benchmark(ep["suite"])()
        task = suite.get_task(ep["task"])
        bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
        env = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=False,
                         has_renderer=False, has_offscreen_renderer=False,
                         horizon=10015, ignore_done=True)
        attach_reset_seed(env)
        started = time.perf_counter()
        try:
            env.seed(ep["seed"])
            env.reset()
            env.set_init_state(suite.get_task_init_states(ep["task"])[ep["seed"]])
            # LIBERO deliberately disables this sensor in the policy's 39-dim
            # proprio aggregate. Read the robot-only sensor for diagnostic
            # geometry without enabling it or changing policy observations.
            site_sensor = env.env._observables["robot0_eef_quat_site"]._sensor
            gripper = env.robots[0].gripper
            components = list(gripper.values()) if isinstance(gripper, dict) else [gripper]
            fingers = {geom for component in components for key, geoms in component.important_geoms.items()
                       if "finger" in key for geom in geoms}
            phases = []
            for label, command in (("open", -1), ("closed", 1), ("reopen", -1)):
                samples = []
                action = np.zeros(7)
                action[-1] = command
                for _ in range(30):
                    obs, _, _, _ = env.step(action)
                    qpos = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32)
                    # Exactly LiberoPrimitives.set_obs's public sensor width.
                    width = float(abs(qpos[0]) + abs(qpos[1]))
                    touching = []
                    for index in range(env.sim.data.ncon):
                        contact = env.sim.data.contact[index]
                        names = [env.sim.model.geom_id2name(int(contact.geom1)),
                                 env.sim.model.geom_id2name(int(contact.geom2))]
                        if any(name in fingers for name in names) and not all(name in fingers for name in names):
                            touching.append(names)
                    samples.append({"opening_m": width, "finger_other_contacts_diagnostic": touching,
                                    "eef_xyz": np.asarray(obs["robot0_eef_pos"]).tolist(),
                                    "eef_quat_site": np.asarray(site_sensor({})).tolist(),
                                    "policy_proprio_dims": int(np.asarray(obs["robot0_proprio-state"]).size)})
                tail = samples[-10:]
                assert not any(sample["finger_other_contacts_diagnostic"] for sample in tail), "empty-jaw tail touched a scene object"
                widths = [sample["opening_m"] for sample in tail]
                (closed_tails if label == "closed" else open_tails).extend(widths)
                phases.append({"name": label, "command": command, "samples": samples,
                               "settled_last10_min_m": min(widths), "settled_last10_max_m": max(widths)})
            row = {"group": group, "episode": ep, "asset": file_identity(bddl), "phases": phases,
                   "source": "robot_joint_proprioception", "private_object_coordinates_saved": False,
                   "wall_s": time.perf_counter() - started}
            rows.append(row)
            (args.output / f"{group}.json").write_text(json.dumps(row, indent=2) + "\n")
            print(json.dumps({"group": group, "empty_calibration_complete": True,
                              "open_min": min(open_tails), "closed_max": max(closed_tails)}), flush=True)
        finally:
            env.close()
    tolerance = float(max(np.ptp(open_tails), np.ptp(closed_tails)))
    calibration = {"closed_empty_max_m": max(closed_tails), "open_empty_min_m": min(open_tails),
                   "max_sensor_opening_m": max(open_tails), "tolerance_m": tolerance,
                   "minimum_points_per_finger": None,
                   "provenance": {"source": "original40_empty_gripper_joint_measurements",
                                  "manifest": file_identity(args.manifest), "output": str(args.output),
                                  "open_samples": len(open_tails), "closed_samples": len(closed_tails),
                                  "geometry_contact_evidence_threshold_not_calibrated": True}}
    report = {"scope": "CPU original reset empty open/closed/reopen; no VLA or task score",
              "script": file_identity(Path(__file__)), "manifest": file_identity(args.manifest),
              "opening_calibration": calibration,
              "grip_site_geometry": panda_static_geometry(Path(xml_path_completion("grippers/panda_gripper.xml"))),
              "rows": rows, "sensor_calibration_complete": True,
              "grasp_verifier_independent_confirmation_complete": False, "new_training_rows": 0,
              "runtime_sim_object_coordinates_used": False}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": file_identity(path), "opening_calibration": calibration,
                      "grip_site_geometry": report["grip_site_geometry"]}, indent=2))


if __name__ == "__main__":
    main()
