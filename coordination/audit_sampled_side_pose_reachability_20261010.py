"""Offline IK diagnostics for recorded public poses; never controls a robot."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def body_transform(body):
    result = np.eye(4)
    w, x, y, z = np.fromstring(body.get("quat", "1 0 0 0"), sep=" ")
    result[:3, :3] = Rotation.from_quat([x, y, z, w]).as_matrix()
    result[:3, 3] = np.fromstring(body.get("pos", "0 0 0"), sep=" ")
    return result


def chain_from_xml(path):
    root = ET.fromstring(path.read_bytes())

    def find(body, parents):
        nodes = parents + [body]
        if body.get("name") == "right_hand":
            return nodes
        for child in body.findall("body"):
            result = find(child, nodes)
            if result is not None:
                return result
        return None

    nodes = find(root.find("worldbody/body"), [])
    joints = [b.find("joint") for b in nodes if b.find("joint") is not None]
    if len(joints) != 7 or any(j.get("type", "hinge") != "hinge" for j in joints):
        raise ValueError("the seven-joint static Panda chain is required")
    if any(not np.allclose(np.fromstring(j.get("pos", "0 0 0"), sep=" "), 0) for j in joints):
        raise ValueError("nonzero hinge offsets need a different FK implementation")
    bounds = np.array([np.fromstring(j.get("range"), sep=" ") for j in joints])

    def fk(q):
        result, index = np.eye(4), 0
        for body in nodes:
            result = result @ body_transform(body)
            joint = body.find("joint")
            if joint is not None:
                axis = np.fromstring(joint.get("axis", "0 0 1"), sep=" ")
                turn = np.eye(4)
                turn[:3, :3] = Rotation.from_rotvec(axis * q[index]).as_matrix()
                result = result @ turn
                index += 1
        return result

    return fk, bounds


def validate_static_fk(path, fk):
    """Compare this diagnostic FK with robot-only MuJoCo, not scene truth."""
    import mujoco
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_hand")
    q = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    for index in range(7):
        joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"joint{index+1}")
        data.qpos[model.jnt_qposadr[joint]] = q[index]
    mujoco.mj_forward(model, data)
    transform = fk(q)
    p_error = float(np.linalg.norm(transform[:3, 3] - data.xpos[body]))
    r_error = float(np.linalg.norm(transform[:3, :3] - data.xmat[body].reshape(3, 3)))
    if p_error > 1e-9 or r_error > 1e-9:
        raise ValueError("static robot FK does not match the installed robot geometry")
    return {"position_error_m": p_error, "rotation_matrix_error": r_error,
            "fixture": "installed robot XML only; no scene, object, or private target"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--robot-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pose", choices=('side_above', 'side_entry', 'contact'), default='side_above')
    args = parser.parse_args()
    fk, bounds = chain_from_xml(args.robot_xml)
    checked = validate_static_fk(args.robot_xml, fk)
    cache, results = {}, []
    for item in map(json.loads, (args.report / "rows.jsonl").open()):
        if item["failure_reason"] != "analytic_sampled_side_above_not_reached":
            continue
        path = Path(item["input"])
        if path not in cache:
            if pin(path)["sha256"] != item["input_sha256"]:
                raise ValueError("closed physical evidence changed")
            cache[path] = list(map(json.loads, path.open()))
        raw = cache[path][item["line"]-1]
        first = raw["first_attempt"]
        receipt = first["receipt"]
        move = next(m for m in first["motion_evidence"] if m.get("analytic_stage") == "sampled_side_above")
        trace = move["trajectory"][0]
        joints = {j["name"]: j["qpos"] for j in trace["contact_and_joints"]["joints"]}
        current = np.array([joints[f"robot0_joint{i+1}"] for i in range(7)])
        step = receipt["geometric_grasp_rankings"][-1]["measurement_step"]
        states_path = Path(raw["output_dir"]) / "states.json"
        state = next(s["state"] for s in json.loads(states_path.read_text())["steps"] if s["step_idx"] == step)
        if np.linalg.norm(np.asarray(trace["eef"]) - state["robot0_eef_pos"]) > .001:
            raise ValueError("public observation and initial robot joint sample are not aligned")
        body = fk(current)
        # eef_pos is the grip site; eef_quat is the hand body. The Panda
        # attachment rotates about z, so the measured site offset stays on z.
        tcp = body[:3, 3] + body[:3, :3] @ np.array([0., 0., .097])
        world_rotation = Rotation.from_quat(state["robot0_eef_quat"]).as_matrix() @ body[:3, :3].T
        world_offset = np.asarray(state["robot0_eef_pos"]) - world_rotation @ tcp
        plan = receipt['analytic_grasp_plan']
        desired_position = np.asarray(move['target_xyz'] if args.pose == 'side_above' else
                                      plan['approach_xyz'] if args.pose == 'side_entry' else plan['xyz'])
        desired_rotation = Rotation.from_quat(move["target_body_quat_xyzw"])

        def residual(q):
            transform = fk(q)
            predicted_position = world_offset + world_rotation @ (
                transform[:3, 3] + transform[:3, :3] @ np.array([0., 0., .097]))
            predicted_rotation = Rotation.from_matrix(world_rotation @ transform[:3, :3])
            return np.r_[predicted_position - desired_position,
                         .15 * (desired_rotation * predicted_rotation.inv()).as_rotvec()]

        seeds = [current, np.array([0., -.4, 0., -2.2, 0., 2., .75]),
                 np.array([.8, -.4, -.8, -2.2, .8, 2., -.75])]
        solves = []
        for seed in seeds:
            solution = least_squares(residual, np.clip(seed, bounds[:, 0]+1e-6, bounds[:, 1]-1e-6),
                bounds=(bounds[:, 0]+1e-6, bounds[:, 1]-1e-6), max_nfev=120,
                ftol=1e-8, xtol=1e-8, gtol=1e-8)
            error = residual(solution.x)
            p, angle = float(np.linalg.norm(error[:3])), float(np.linalg.norm(error[3:])/.15)
            solves.append({"position_error_m": p, "orientation_error_rad": angle,
                "joint_margin_min_rad": float(np.min(np.minimum(solution.x-bounds[:, 0], bounds[:, 1]-solution.x))),
                "joint_angles": solution.x.tolist(), "function_evaluations": solution.nfev,
                "solution_found": p < .008 and angle < .05})
            if solves[-1]["solution_found"]:
                break
        results.append({"case": item["case"], "state_sha256": item["state_sha256"],
            "physical_input": {**pin(path), "line": item["line"]},
            "public_state": pin(states_path), "target_xyz_public": desired_position.tolist(),
            "target_body_quat_public": move["target_body_quat_xyzw"],
            "audited_pose": args.pose,
            "robot_base_from_recorded_proprioception": {"rotation": world_rotation.tolist(), "offset": world_offset.tolist()},
            "solves": solves, "solution_found": any(s["solution_found"] for s in solves),
            "not_found_is_not_proof_of_infeasibility": True,
            "self_collision_or_scene_collision_checked": False,
            "diagnostic_only": True, "training_allowed": False})
        print(json.dumps({"case": item["case"], "solution_found": results[-1]["solution_found"]}), flush=True)
    args.output.mkdir(parents=True, exist_ok=False)
    records = args.output / "rows.jsonl"
    records.write_text("".join(json.dumps(r) + "\n" for r in results))
    manifest = {"producer": pin(Path(__file__)), "robot_xml": pin(args.robot_xml),
        "audited_pose": args.pose,
        "static_fk_validation": checked, "input": pin(args.report / "rows.jsonl"),
        "records": pin(records), "n": len(results),
        "numerical_solution_found": sum(r["solution_found"] for r in results),
        "no_numerical_solution_found": sum(not r["solution_found"] for r in results),
        "limits": ["A failed numerical solve is not proof of infeasibility.",
                   "IK feasibility does not certify a collision-free or tracked servo path.",
                   "Saved diagnostic joint samples are robot proprioception, never object coordinates; this audit does not feed a runtime policy."],
        "qualification_allowed": False, "training_allowed": False}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
