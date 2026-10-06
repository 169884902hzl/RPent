"""Measure stove controls in original scenes after fixed real on/off skills.

Private predicates and actuator qpos are written only to diagnostic labels.
They never select a skill, stop contact execution, or construct a public pose.
No simulation state or asset is modified by this measurement experiment.
"""

import argparse
from collections import Counter
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import time

from scripts.probe_v5_skill501_original import diagnostic_json, executed_actions, public_observation


CONTROL_FEATURE_QUERIES = {
    "pivot": "stove switch pivot", "tip": "stove switch lever tip",
    "shell": "stove", "front_edge": "front edge of the stove",
}


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_manifest(plan):
    if (plan["version"] not in ("original-stove-control-measurement/1-dev", "original-stove-control-measurement/2-fullchunks-dev",
                                "original-stove-control-measurement/3-directed-control-dev")
            or plan["planned_episodes"] != 10 or plan["planned_contact_skills"] != 20
            or plan["budget"] != {"max_chunks_per_skill": 160, "actions_per_chunk": 5, "max_episode_steps": 10000}
            or plan["capture_views"] != ["agentview", "wrist"]
            or plan["control_queries"] != ["stove knob", "stove switch handle"]):
        raise ValueError("registered original measurement protocol changed")
    if plan["phases"] != [{"name": "initial", "mode": None, "prompt": None},
                          {"name": "on", "mode": "turn_on", "prompt": "turn on the stove"},
                          {"name": "off", "mode": "turn_off", "prompt": "turn off the stove"}]:
        raise ValueError("fixed initial/on/off sequence changed")
    expected = [{"suite": "libero_goal", "task": 7, "seed": seed} for seed in range(10)]
    if [case["episode"] for case in plan["cases"]] != expected:
        raise ValueError("only the registered original initial states may be opened")
    if any(case["original_instruction"] != "turn on the stove" for case in plan["cases"]):
        raise ValueError("registered original instruction changed")
    if plan["version"] in ("original-stove-control-measurement/2-fullchunks-dev", "original-stove-control-measurement/3-directed-control-dev"):
        if (plan.get("diagnostic_server_module") != "robots.libero.v5_stove_probe_env"
                or plan.get("full_chunk_diagnostic_scope") is not True):
            raise ValueError("full chunks require the independent registered diagnostic facade")
    if plan.get("stove_control_features_v1"):
        if plan.get("control_feature_queries") != CONTROL_FEATURE_QUERIES:
            raise ValueError("directed measurements require the explicit registered feature queries")
    if plan["version"] == "original-stove-control-measurement/3-directed-control-dev" and not plan.get("stove_control_features_v1"):
        raise ValueError("directed-control protocol requires its measurement switch")


def control_geometry(points):
    """Report current measured geometry and fit quality without an endpoint label."""
    import numpy as np

    points = np.asarray(points, dtype=float)
    result = {"src": "perception", "points": len(points), "endpoint_state": "unmeasured",
              "interpretation": "independent current SAM/depth candidate, not a verified control endpoint"}
    if len(points) < 3:
        return {**result, "reason": "insufficient_current_depth"}
    lower, upper = np.quantile(points, (.02, .98), axis=0)
    centre = np.median(points, axis=0)
    _, singular, axes = np.linalg.svd(points[:, :2] - centre[:2], full_matrices=False)
    angle = float(np.degrees(np.arctan2(axes[0, 1], axes[0, 0])) % 180)
    return {**result, "centre_xyz_m": centre.tolist(), "lower_xyz_m": lower.tolist(),
            "upper_xyz_m": upper.tolist(), "vertical_span_m": float(upper[2] - lower[2]),
            "undirected_axis_xy": axes[0].tolist(), "orientation_deg_mod180": angle,
            "xy_singular_values": singular.tolist(),
            "axis_elongation_ratio": float(singular[0] / singular[1]) if singular[1] > 1e-12 else None}


def private_labels(rpc, case):
    """Read both modes at the same stationary observation; never step physics."""
    return {"scope": "diagnostic_labels_only_not_controller_input",
            "requested_predicates": {mode: rpc.call("oracle.skill501_truth", kwargs={"spec": {
                "kind": "articulate", "mode": mode,
                "object_symbol": case["object_symbol_for_labels_only"]}}, timeout_s=120)
                for mode in ("turn_on", "turn_off")}}


def bind_current_control_features(candidates, shell, camera_xyz, *, source_step, camera):
    """Bind only unique current public candidates; never consume private labels."""
    import numpy as np
    from robots.libero.v5_perception_geometry import same_segmented_instance
    from robots.libero.v5_stove_measurement import CONTROL_FEATURE_VERSION, measure_stove_control_features

    result = {"version": CONTROL_FEATURE_VERSION, "src": "perception", "source_step": source_step,
              "camera": camera, "parent": shell.id if shell else None,
              "control_pose": None, "directed_lever": None, "stove_reference": None,
              "signed_angle_to_reference_deg": None, "endpoint_state": "unmeasured"}
    if shell is None:
        return {**result, "reason": "current_unique_stove_shell_not_measured"}
    controls, masks = [], []
    for candidate in candidates["control"]:
        if any(same_segmented_instance(candidate["mask"], mask) for mask in masks):
            candidate["record"]["binding"] = {"reason": "same_current_control_mask"}
            continue
        measured = measure_stove_control_features(candidate["points"], shell, camera_xyz,
            source_step=source_step, camera=camera)
        candidate["record"]["binding"] = {"parent": shell.id, "source_step": source_step,
            "camera": camera, "control_geometry": measured.get("control_geometry"), "reason": measured["reason"]}
        if measured["control_pose"] is not None:
            controls.append((candidate, measured))
            masks.append(candidate["mask"])
    result["valid_control_candidates"] = len(controls)
    if len(controls) != 1:
        return {**result, "reason": "no_valid_current_control" if not controls else "multiple_valid_current_controls"}
    control, measured = controls[0]
    bound, selected, feature_binding = {}, {}, {}
    for role in CONTROL_FEATURE_QUERIES:
        accepted, role_masks = [], []
        for candidate in candidates[role]:
            cloud = candidate["points"]
            if len(cloud) < 20:
                candidate["record"]["binding"] = {"reason": "feature_current_depth_insufficient"}
                continue
            centre = np.median(cloud, axis=0)
            lower, upper = (measured["control_geometry"]["lower"], measured["control_geometry"]["upper"]) if role in ("pivot", "tip") else (shell.lower, shell.upper)
            margin = .006 if role in ("pivot", "tip") else .03
            if np.any(centre < np.asarray(lower) - margin) or np.any(centre > np.asarray(upper) + margin):
                candidate["record"]["binding"] = {"reason": "feature_outside_current_bound_control_or_shell"}
                continue
            if any(same_segmented_instance(candidate["mask"], mask) for mask in role_masks):
                candidate["record"]["binding"] = {"reason": "same_current_feature_mask"}
                continue
            if role in ("pivot", "tip") and same_segmented_instance(candidate["mask"], control["mask"]):
                candidate["record"]["binding"] = {"reason": "feature_not_distinct_from_current_control"}
                continue
            candidate["record"]["binding"] = {"parent": shell.id, "source_step": source_step,
                                               "camera": camera, "reason": "current_attached_feature_candidate"}
            accepted.append(candidate)
            role_masks.append(candidate["mask"])
        feature_binding[role] = {"valid_candidates": len(accepted), "reason": "unique_current_feature" if len(accepted) == 1
                                else "no_valid_current_feature" if not accepted else "multiple_valid_current_features"}
        if len(accepted) == 1:
            selected[role] = accepted[0]
            bound[role] = accepted[0]["points"]
    for first, second in (("pivot", "tip"), ("shell", "front_edge")):
        if first in selected and second in selected and same_segmented_instance(selected[first]["mask"], selected[second]["mask"]):
            for role in (first, second):
                bound.pop(role, None)
                feature_binding[role]["reason"] = "directed_feature_masks_not_distinct"
    measured = measure_stove_control_features(control["points"], shell, camera_xyz,
        source_step=source_step, camera=camera, feature_points=bound)
    return {**measured, "valid_control_candidates": 1, "feature_binding": feature_binding,
            "bound_control_cloud": control["record"]["cloud"],
            "feature_clouds": {role: selected[role]["record"]["cloud"] for role in bound}}


def capture_measurements(executor, sam_rpc, oracle_rpc, case, plan, destination, *, capture):
    """Save immutable per-view evidence, without treating cached support as visibility."""
    import base64
    from io import BytesIO
    import numpy as np
    from PIL import Image
    from robots.libero.v5_perception_geometry import measured_points
    from robots.libero.v5_state import entity_record
    from robots.libero.v5_stove_measurement import measure_stove_rgbd
    from rpent.robots.components.sam3_client import Sam3Client

    feature_measurements = bool(plan.get("stove_control_features_v1", False))
    destination.mkdir(parents=True, exist_ok=False)
    if capture:
        executor.capture()
        executor.scene.refresh(["stove"])
    state = executor.toolkit._state
    step = state.latest_step
    public = public_observation(executor)
    current_stoves = [e for e in executor.scene.entities.values()
                      if e.name == "stove" and e.visible and e.source_step == step]
    shell = current_stoves[0] if len(current_stoves) == 1 else None
    public_record = {"source_step": step, "views": {}, "public_observation": public,
                     "current_stove_shell": entity_record(shell) if shell else None,
                     "current_shell_count": len(current_stoves), "control_views_fused": False,
                     "cached_support_used_as_current_visibility": False}
    # These read-only labels refer to the saved observation and do not change
    # contact execution, geometry, candidate selection or endpoint verdicts.
    labels = private_labels(oracle_rpc, case)
    labels.update(source_step=step)
    (destination / "labels.json").write_text(diagnostic_json(labels, indent=2) + "\n")
    for camera in plan["capture_views"]:
        image_bytes = state.load_bytes(f"{camera}_high.png", step=step)
        image = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
        world = state.load(f"{camera}_world_high.npz", step=step)
        metadata = state.load(f"{camera}_metadata.json", step=step)
        view_dir = destination / camera
        view_dir.mkdir()
        rgb_path, world_path, metadata_path = view_dir / "rgb.png", view_dir / "world.npz", view_dir / "metadata.json"
        rgb_path.write_bytes(image_bytes)
        np.savez_compressed(world_path, array=world)
        metadata_path.write_text(diagnostic_json(metadata, indent=2) + "\n")
        view = {"camera": camera, "source_step": step, "image_shape": list(image.shape[:2]),
                "coordinate_source": "current_calibrated_rgbd_camera_to_world",
                "files": {"rgb": identity(rgb_path), "world": identity(world_path), "metadata": identity(metadata_path)},
                "queries": [], "coil_packet": None,
                "stove_shell_is_not_control_mask": True}
        if shell is not None:
            view["coil_packet"] = measure_stove_rgbd(image, world, shell, step, camera)
        else:
            view["coil_reason"] = "current_unique_stove_shell_not_measured"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        queries = [("control", prompt) for prompt in plan["control_queries"]]
        if feature_measurements:
            queries += list(plan["control_feature_queries"].items())
        candidates = {role: [] for role in ("control", *CONTROL_FEATURE_QUERIES)}
        for query_index, (role, prompt) in enumerate(queries):
            response = sam_rpc.call("sam3.segment_all", kwargs={
                "image_base64": encoded, "text_prompt": prompt, "min_score": plan["sam_min_score"]}, timeout_s=120)
            query = {"prompt": prompt, "minimum_score": plan["sam_min_score"], "instances": []}
            if feature_measurements:
                query["feature_role"] = role
            for instance_index, item in enumerate(response.get("instances", [])):
                decoded = Sam3Client._decode_result(item)
                if decoded.mask is None or decoded.mask.shape != image.shape[:2]:
                    if feature_measurements:
                        query["instances"].append({"id": f"c{query_index}_{instance_index}",
                            "score": decoded.score, "reason": "current_feature_mask_missing_or_wrong_shape"})
                        continue
                    raise ValueError("control SAM mask does not match the saved view")
                cloud = measured_points(world, decoded.mask)
                stem = f"query{query_index}_instance{instance_index}"
                mask_path, cloud_path = view_dir / (stem + "_mask.png"), view_dir / (stem + "_cloud.npz")
                Image.fromarray(decoded.mask.astype(np.uint8) * 255).save(mask_path)
                np.savez_compressed(cloud_path, array=cloud)
                instance = {
                    "id": f"c{query_index}_{instance_index}", "score": decoded.score,
                    "mask_pixels": int(decoded.mask.sum()), "valid_depth_points": len(cloud),
                    "valid_depth_fraction": len(cloud) / max(1, int(decoded.mask.sum())),
                    "mask": identity(mask_path), "cloud": identity(cloud_path),
                    "geometry": control_geometry(cloud)}
                query["instances"].append(instance)
                candidates[role].append({"points": cloud, "mask": decoded.mask, "record": instance})
            view["queries"].append(query)
        if feature_measurements:
            camera_xyz = np.asarray(metadata["extrinsic_cam2world"])[:3, 3]
            view["control_features"] = bind_current_control_features(candidates, shell, camera_xyz,
                source_step=step, camera=camera)
        public_record["views"][camera] = view
    if feature_measurements:
        public_record["control_feature_measurements_v1"] = True
        public_record["control_parent_binding"] = {"parent": shell.id if shell else None, "source_step": step,
            "same_capture_views": plan["capture_views"], "reason": "unique_current_measured_stove" if shell else
            "current_unique_stove_shell_not_measured"}
    packet = destination / "public_measurements.json"
    packet.write_text(diagnostic_json(public_record, indent=2) + "\n")
    return {"public_measurements": identity(packet), "labels": identity(destination / "labels.json"),
            "source_step": step, "query_instances_by_view": {
                camera: [len(query["instances"]) for query in view["queries"]]
                for camera, view in public_record["views"].items()}}


def run_phases(executor, sam_rpc, oracle_rpc, case, plan, output):
    """Run all fixed phases regardless of private success; preserve each failure."""
    phases = []
    with executor.p.env.complete_skill():
        for phase in plan["phases"]:
            directory = output / phase["name"]
            directory.mkdir()
            row = {"phase": phase["name"], "mode": phase["mode"], "prompt": phase["prompt"],
                   "first_attempt": None, "pre_recovery": None, "post_recovery": None}
            if phase["mode"] is not None:
                if plan.get("stove_control_features_v1"):
                    row["before_contact"] = capture_measurements(
                        executor, sam_rpc, oracle_rpc, case, plan, directory / "before_contact", capture=True)
                executor.motion_evidence = []
                start = time.perf_counter()
                scope_started = False
                try:
                    if plan.get("full_chunk_diagnostic_scope"):
                        oracle_rpc.call("diagnostic.stove_chunk_start", kwargs={
                            "phase": phase["name"], "max_chunks": plan["budget"]["max_chunks_per_skill"]}, timeout_s=120)
                        scope_started = True
                    receipt = executor.vla_act(phase["prompt"], plan["budget"]["max_chunks_per_skill"], "chunk_budget")
                    row["first_attempt"] = {"selected": "vla_act", "prompt": phase["prompt"],
                        "receipt": receipt, "motion_evidence": copy.deepcopy(executor.motion_evidence),
                        "executed_control_actions": executed_actions(executor.motion_evidence),
                        "wall_s": time.perf_counter() - start}
                except Exception as error:
                    row["first_attempt"] = {"selected": "vla_act", "prompt": phase["prompt"],
                        "status": "execution_error", "error": repr(error),
                        "motion_evidence": copy.deepcopy(executor.motion_evidence),
                        "executed_control_actions": executed_actions(executor.motion_evidence),
                        "wall_s": time.perf_counter() - start}
                finally:
                    if scope_started:
                        row["first_attempt"]["chunk_completion_scope"] = oracle_rpc.call(
                            "diagnostic.stove_chunk_end", timeout_s=120)
                executor.capture()
                executor.scene.refresh(["stove"])
            row["pre_recovery"] = capture_measurements(
                executor, sam_rpc, oracle_rpc, case, plan, directory / "pre_recovery", capture=False)
            executor.motion_evidence = []
            try:
                released = executor.p.release()
                executor.retreat()
                row["public_recovery"] = {"release": released, "retreat": "existing_measured_view_recovery",
                                          "motion_evidence": copy.deepcopy(executor.motion_evidence)}
            except Exception as error:
                row["public_recovery"] = {"status": "execution_error", "error": repr(error),
                                          "motion_evidence": copy.deepcopy(executor.motion_evidence)}
            row["post_recovery"] = capture_measurements(
                executor, sam_rpc, oracle_rpc, case, plan, directory / "post_recovery", capture=True)
            (directory / "phase.json").write_text(diagnostic_json(row, indent=2) + "\n")
            phases.append(row)
    return {"phases": phases, "status": "all_fixed_phases_recorded",
            "native_original_success_latched": bool(executor.p.env._native_terminated),
            "external_action_budget_exhausted": bool(executor.p.env.truncated)}


def run_case(case, base, plan, endpoints, output):
    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category, scene_vocabulary
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    cfg = {**base, **case["episode"], "motion_trace_v1": True}
    events = NullDashboardEventSink()
    port = pick_free_port()
    endpoint = f"http://127.0.0.1:{port}"
    server_module = plan.get("diagnostic_server_module", "scripts.probe_v5_skill501_original")
    daemon = ProcessDaemon(name="stove521_original", cmd=[sys.executable, "-m", server_module, "--serve",
        "--suite", cfg["suite"], "--task", str(cfg["task"]), "--seed", str(cfg["seed"]),
        "--max-episode-steps", str(plan["budget"]["max_episode_steps"]), "--port", str(port)],
        log_path=str(output / "oracle_env.log"))
    toolkit, daemons = None, []
    try:
        daemon.start()
        oracle_rpc = HttpRpcClient(endpoint)
        wait_for_ready(oracle_rpc, daemon=daemon, timeout_s=300)
        runtime_args = argparse.Namespace(**case["episode"], libero_type="standard",
            max_episode_steps=plan["budget"]["max_episode_steps"], env_endpoint=endpoint,
            env_client_class=V5SkillEnvClient, sam3_endpoint=endpoints["sam3"], vla_endpoint=endpoints["vla"],
            molmo_endpoint=None, cuda_device=None, planner="typed_choice", collect_flywheel_data=False)
        daemons, runtime = _init_runtime(runtime_args, output, events, None)
        toolkit = LiberoToolkit(runtime_kwargs=runtime, dashboard_events=events,
                               memory=MemoryManager(output / "empty_memory", memory_access="read_only"), state_output_dir=output)
        scene_flags = {name: cfg[name] for name in inspect.signature(MeasuredScene).parameters
                       if name in cfg and name not in {"toolkit", "rpc", "seed"}}
        sam_rpc = HttpRpcClient(endpoints["sam3"])
        scene = MeasuredScene(toolkit, sam_rpc, cfg["seed"], **scene_flags)
        executor_flags = {name: cfg[name] for name in inspect.signature(V5Executor).parameters
                          if name in cfg and name not in {"toolkit", "scene", "max_chunks", "instruction"}}
        executor = V5Executor(toolkit, scene, plan["budget"]["max_chunks_per_skill"], **executor_flags)
        initial = toolkit.execute_tool("view_env_state", {}).result
        if initial["task_language"] != case["original_instruction"]:
            raise ValueError("running original instruction does not match the manifest")
        executor.instruction = scene.instruction = initial["task_language"]
        scene.instance_limits = Counter(category(name) for name in initial["state"]["object_names"])
        scene.refresh(scene_vocabulary(initial["state"]["object_names"], executor.instruction))
        return run_phases(executor, sam_rpc, oracle_rpc, case, plan, output)
    finally:
        if toolkit is not None:
            toolkit.close()
        for owned in reversed(daemons):
            owned.stop()
        daemon.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.shards != 4 or not 0 <= args.shard_index < args.shards:
        parser.error("the registered 4-shard experiment requires shard-index 0..3")
    plan = json.loads(args.manifest.read_text())
    validate_manifest(plan)
    config = Path(plan["base_config"]["path"])
    if identity(config)["sha256"] != plan["base_config"]["sha256"]:
        raise ValueError("registered original base config changed")
    base = json.loads(config.read_text())
    if base["libero_type"] != "standard" or os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("standard original LIBERO only")
    from rlinf.envs.libero.utils import benchmark
    import numpy as np
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints = [], {}
    try:
        for name, module, extra in (("sam3", "robots.libero.v5_sam3_server", []),
                                  ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"])):
            port = pick_free_port()
            daemon = ProcessDaemon(name="stove521_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http", "--host", "127.0.0.1",
                     "--port", str(port), "--parent-watch"], log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for case in plan["cases"][args.shard_index::args.shards]:
                for field in ("bddl", "init_file"):
                    if identity(case[field]["path"])["sha256"] != case[field]["sha256"]:
                        raise ValueError("registered original asset changed: " + field)
                state = benchmark.get_benchmark("libero_goal")().get_task_init_states(7)[case["episode"]["seed"]]
                if hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest() != case["state_sha256"]:
                    raise ValueError("registered original initial state changed")
                output = args.output / case["name"]
                output.mkdir()
                row = {"case": case, "output_dir": str(output), "new_training_rows": 0}
                started = time.perf_counter()
                try:
                    row.update(run_case(case, base, plan, endpoints, output))
                except Exception as error:
                    row.update(status="probe_error", error=repr(error))
                row["wall_s"] = time.perf_counter() - started
                (output / "episode.json").write_text(diagnostic_json(row, indent=2) + "\n")
                ledger.write(diagnostic_json(row) + "\n")
                ledger.flush()
                print(diagnostic_json({"case": case["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
                if row["status"] == "probe_error":
                    raise RuntimeError("preserved original development probe error; repair before continuing")
    finally:
        for daemon in reversed(daemons):
            daemon.stop()


if __name__ == "__main__":
    main()
