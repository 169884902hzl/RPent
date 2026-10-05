"""Owned original-task first-grasp, place and fixture trials with metrology.

Each trial resets its registered official state. Setup uses real measured
skills; the first tested skill is recorded separately. Private joint and
predicate measurements never change the executor's receipt or stop rule.
"""

import argparse
from collections import Counter
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
import time
import types
from contextlib import contextmanager


ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}
PROBE_MODULE = "scripts.probe_v5_skill501_original"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnostic_json(value, *, indent=None):
    """Preserve private RPC NumPy arrays/scalars as JSON values at write time."""
    import numpy as np
    def convert(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"Unsupported diagnostic field: {type(item).__name__}")
    return json.dumps(value, default=convert, allow_nan=False, ensure_ascii=False, indent=indent)


def private_skill_truth(wrapper, spec):
    """Read official original predicates and actual fixture joints, without stepping."""
    env = wrapper.env
    mode = spec["mode"]
    predicate = {"turn_on": "turnon", "turn_off": "turnoff"}.get(mode, mode)
    goal = [predicate, spec["object_symbol"]]
    if spec["kind"] in {"place", "grasp_then_subtask"}:
        goal.append(spec["target_symbol"])
    state = env.object_states_dict.get(spec["object_symbol"])
    joint_state = None
    joint_names = []
    if spec["kind"] == "articulate" and state is not None:
        if state.object_state_type == "site":
            site = env.object_sites_dict[spec["object_symbol"]]
            joint_names = list(site.joints)
            if not joint_names:
                state = env.object_states_dict[state.parent_name]
                joint_names = list(env.fixtures_dict[state.object_name].joints)
                goal[1] = state.object_name
        else:
            obj = env.fixtures_dict.get(spec["object_symbol"], env.objects_dict.get(spec["object_symbol"]))
            joint_names = list(obj.joints) if obj is not None else []
        # SiteObjectState has no get_joint_state implementation. In particular,
        # drawer sites must read their own joints instead of every parent joint.
        import numpy as np
        joint_state = [np.asarray(env.sim.data.get_joint_qpos(name)).reshape(-1).tolist()
                       for name in joint_names]
    return {"source": "simulation_diagnostic_only", "predicate": goal,
            "satisfied": bool(env._eval_predicate(goal)), "joint_names": joint_names,
            "joint_qpos": joint_state, "sim_time": float(env.sim.data.time)}


def private_grasp_trace_summary(reference, samples, duration_s=.5):
    """Keep intermediate sustained grasp distinct from final release/transfer.

    Samples are taken at every actual simulator control step. They never
    stop the VLA or supply public geometry or verification results.
    """
    from robots.libero.v5_grasp_truth import sustained_grasp
    window, first_success = [], None
    supports = set(reference["other_contact_geoms"])
    for sample in samples:
        supported = (sample["lower_extent_m"] - reference["lower_extent_m"] >= .03
                     and sample["finger_contact"]
                     and not (supports & set(sample["other_contact_geoms"])))
        if not supported:
            window = []
            continue
        window.append(sample)
        if first_success is None and sample["sim_time"] - window[0]["sim_time"] + 1e-8 >= duration_s:
            first_success = {"start_sim_time": window[0]["sim_time"],
                             "end_sim_time": sample["sim_time"],
                             "truth": sustained_grasp(window, reference, duration_s)}
    final_hold = sustained_grasp(window, reference, duration_s) if window else None
    return {"source": "simulation_diagnostic_only", "control_steps_sampled": len(samples),
            "reference": reference, "samples": samples,
            "true_sustained_grasp_during_skill": first_success is not None,
            "first_sustained_grasp": first_success,
            "true_sustained_grasp_at_end": bool(final_hold and final_hold["success"]),
            "final_hold_window": final_hold,
            "interpretation": "a subsequent successful release does not erase earlier sustained grasp"}


def attach_skill_grasp_trace(worker):
    """Collect private contact evidence without modifying a single action."""
    from robots.libero.v5_grasp_truth import contact_sample
    original_step = worker.step
    worker._skill501_grasp_trace = None

    def step(self, action):
        result = original_step(action)
        trace = self._skill501_grasp_trace
        if trace is not None:
            trace["samples"].append(contact_sample(self.env, trace["name"]))
        return result

    def begin(self, name):
        if self._skill501_grasp_trace is not None:
            raise ValueError("a private first-skill contact trace is already active")
        reference = contact_sample(self.env, name)
        self._skill501_grasp_trace = {"name": name, "reference": reference, "samples": []}
        return reference

    def finish(self):
        trace = self._skill501_grasp_trace
        self._skill501_grasp_trace = None
        if trace is None:
            raise ValueError("no private first-skill contact trace is active")
        return private_grasp_trace_summary(trace["reference"], trace["samples"])

    worker.step = types.MethodType(step, worker)
    worker.v5_skill501_grasp_trace_begin = types.MethodType(begin, worker)
    worker.v5_skill501_grasp_trace_finish = types.MethodType(finish, worker)
    return worker


def public_observation(executor):
    """Snapshot only data already available to the measured controller."""
    from robots.libero.v5_state import entity_record
    return {"entities": [entity_record(e) for e in executor.scene.entities.values()],
            "robot": {"eef_xyz": list(map(float, executor.p._last_obs_eef_pos)),
                      "gripper_opening": float(executor.p._last_obs_gripper),
                      "held": executor.held}}


def executed_actions(motions):
    """A selected or acknowledged tool is not evidence of physical execution."""
    return sum(int(move.get("executed_action_count", move.get("steps_used", 0)))
               for move in motions)


def make_probe_env(task_id, seed, suite_name, max_episode_steps):
    """Own the private metrology worker; leave the shared oracle implementation intact."""
    from rlinf.envs.libero.libero_env import LiberoEnv
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.env_server import build_env_cfg

    suite = benchmark.get_benchmark(suite_name)()
    trials = len(suite.get_task_init_states(task_id))
    if not 0 <= seed < trials:
        raise ValueError("official initial-state index out of range; no modulo substitution")
    first_id = sum(len(suite.get_task_init_states(task)) for task in range(task_id))
    cfg = build_env_cfg(task_suite_name=suite_name, specific_reset_id=first_id + seed,
                        seed=seed, max_episode_steps=max_episode_steps)
    cfg.init_params.ignore_done = True

    class SkillProbeEnv(LiberoEnv):
        def get_env_fns(self):
            from robots.libero.v5_branch_state import attach_branch_state
            from robots.libero.v5_reset_seed import attach_reset_seed
            from robots.libero.v5_motion_diagnostics import attach_motion_diagnostic
            def create(factory):
                worker = attach_branch_state(attach_motion_diagnostic(attach_reset_seed(factory())))
                worker.v5_skill501_truth = types.MethodType(private_skill_truth, worker)
                return attach_skill_grasp_trace(worker)
            return [lambda factory=factory: create(factory) for factory in super().get_env_fns()]

    return SkillProbeEnv(cfg=cfg, num_envs=1, seed_offset=0, total_num_processes=1, worker_info=None)


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--suite", choices=sorted(ORIGINAL_SUITES), required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-episode-steps", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard required for owned original metrology")
    from robots.libero.v5_oracle_server import OriginalOracleFacade
    from rpent.utils.serialization import to_numpy_tree

    class SkillFacade(OriginalOracleFacade):
        def _register_rpc(self):
            super()._register_rpc()
            self._rpc["oracle.skill501_truth"] = self.skill_truth
            self._readonly_methods.add("oracle.skill501_truth")
            self._rpc["oracle.skill501_grasp_trace_begin"] = self.grasp_trace_begin
            self._rpc["oracle.skill501_grasp_trace_finish"] = self.grasp_trace_finish
            self._readonly_methods.update(("oracle.skill501_grasp_trace_begin", "oracle.skill501_grasp_trace_finish"))
        def skill_truth(self, spec):
            return to_numpy_tree(self._env.env.workers[0].env_call(
                "v5_skill501_truth", args=[spec], target="self"))
        def grasp_trace_begin(self, name):
            return to_numpy_tree(self._env.env.workers[0].env_call(
                "v5_skill501_grasp_trace_begin", args=[name], target="self"))
        def grasp_trace_finish(self):
            return to_numpy_tree(self._env.env.workers[0].env_call(
                "v5_skill501_grasp_trace_finish", target="self"))

    env = make_probe_env(args.task, args.seed, args.suite, args.max_episode_steps)
    SkillFacade(env, meta={"suite": args.suite, "task": args.task, "seed": args.seed,
                           "max_episode_steps": args.max_episode_steps,
                           **({"original90_grasp_diagnostic_v1": True} if args.suite == "libero_90" else {})}, motion_trace_v1=True,
                original90_diagnostic=args.suite == "libero_90").serve(
                    transport="http", host="127.0.0.1", port=args.port, parent_watch=True)


def registered_drawer_instruction(spec):
    """Keep the registered public ordinal; do not infer one from a symbol."""
    if spec.get("mode") not in {"open", "close"}:
        return None
    category = spec.get("object_category", "")
    if not re.fullmatch(r"cabinet (?:top|upper|middle|bottom|lower) drawer", category):
        return None
    instruction = spec.get("subtask_prompt", f"{spec['mode']} the {category}")
    ordinal = re.search(r"\b(top|upper|middle|bottom|lower) drawer\b", instruction, re.IGNORECASE)
    expected = re.search(r"\b(top|upper|middle|bottom|lower) drawer\b", category)
    def normalize(value):
        return {"upper": "top", "lower": "bottom"}.get(value.lower(), value.lower())
    if (ordinal is None or normalize(ordinal[1]) != normalize(expected[1])
            or not re.match(spec["mode"] + r"\b", instruction, re.IGNORECASE)):
        raise ValueError("registered public drawer subtask contradicts its declared category/mode")
    return instruction


def bind_action(executor, policy, spec, tool):
    """An oracle may name a target; its motion binding uses public measurements only."""
    from robots.libero.v5_state import Candidate
    if tool == "retreat":
        return Candidate(tool)
    entities = list(executor.scene.entities.values())
    instruction = spec.get("subtask_prompt", executor.instruction)
    obj = policy.bind(spec["object_symbol"], entities, instruction, executor.scene.view_axes)
    if obj is None and tool == "articulate" and registered_drawer_instruction(spec) is not None:
        cabinets = [entity for entity in entities if entity.visible and entity.name == "cabinet"]
        if len(cabinets) == 1:
            # The ordinary original expert already uses this coarse selector.
            # The executor preserves the public middle/top/bottom phrase; no
            # drawer entity, handle pose or simulator geometry is fabricated.
            obj = cabinets[0]
            policy.last_binding = {
                "source_entity": obj.id, "basis": "unique_measured_cabinet_public_drawer_instruction",
                "public_condition_instruction": registered_drawer_instruction(spec),
            }
    if obj is None:
        raise LookupError("source entity missing or ambiguous in public measurements")
    target = None
    if spec.get("target_symbol"):
        target = policy.bind(spec["target_symbol"], entities, instruction,
                             executor.scene.view_axes, source_reference=False)
        if target is None:
            raise LookupError("target entity missing or ambiguous in public measurements")
    return Candidate(tool, obj.id, target.id if target else None, spec["mode"])


def execute_measured_offset(executor, spec):
    """Move by a registered offset from current public robot proprioception."""
    import numpy as np

    before = public_observation(executor)
    start_xyz = np.asarray(executor.p._last_obs_eef_pos, dtype=float).copy()
    target = start_xyz + np.asarray(spec["offset_m"], dtype=float)
    executor.motion_evidence = []
    started = time.perf_counter()
    motion = executor.move(target.tolist(), spec["gripper"], tolerance_m=.02, recoverable=True)
    executor.capture()
    executor._refresh(sorted(executor.scene.vocabulary))
    reached = motion.get("waypoint_reached") is True
    motions = copy.deepcopy(executor.motion_evidence)
    actions = executed_actions(motions)
    return {"phase": "setup", "selected": "measured_offset",
            "public_before": before, "public_after": public_observation(executor),
            "pose_source": "current_public_robot_eef_proprioception",
            "start_xyz": start_xyz.tolist(), "offset_m": list(spec["offset_m"]),
            "target_xyz": target.tolist(), "motion_evidence": motions,
            "receipt": {"tool": "measured_offset", "executed": actions > 0,
                        "verification": "executed" if reached else "failed",
                        "waypoint_reached": reached, "motion": copy.deepcopy(motion)},
            "executed_actions": actions, "physically_executed": actions > 0,
            "wall_s": time.perf_counter() - started}


def execute_stage(executor, policy, rpc, spec, tool, phase, *, contact_evidence=None, action=None):
    """Keep public controller evidence separate from private post-execution labels."""
    spec = {**spec, "kind": spec.get("kind", spec.get("tool"))}
    action = action or bind_action(executor, policy, spec, tool)
    record = {"phase": phase, "selected": action.text(),
              "public_before": public_observation(executor),
              "held_before": executor.held}
    support_reference = None
    if spec["kind"] == "grasp":
        support_reference = rpc.call("oracle.grasp_reference",
                                     kwargs={"name": spec["object_symbol"]}, timeout_s=120)
    if spec.get("kind") in {"place", "articulate", "grasp_then_subtask"}:
        record["private_before"] = rpc.call("oracle.skill501_truth", kwargs={"spec": spec}, timeout_s=120)
    original_instruction = executor.instruction
    public_instruction = registered_drawer_instruction(spec) if tool == "articulate" else None
    if public_instruction is not None:
        executor.instruction = public_instruction
        record["contact_instruction"] = {
            "original": original_instruction, "effective": public_instruction,
            "origin": "registered_original_public_subtask",
            "scoped_override": original_instruction != public_instruction,
        }
        record["binding_evidence"] = copy.deepcopy(getattr(policy, "last_binding", {}))
    start = time.perf_counter()
    try:
        receipt = executor.execute(action)
    finally:
        executor.instruction = original_instruction
    record.update(receipt=copy.deepcopy(receipt), wall_s=time.perf_counter() - start,
                  held_after=executor.held, motion_evidence=copy.deepcopy(executor.motion_evidence),
                  verification_measurements=copy.deepcopy(executor.last_verification_measurements),
                  public_after=public_observation(executor))
    if contact_evidence is not None:
        record["contact_evidence"] = copy.deepcopy(contact_evidence)
    if spec.get("kind") in {"place", "articulate", "grasp_then_subtask"}:
        try:
            record["private_after"] = rpc.call("oracle.skill501_truth", kwargs={"spec": spec}, timeout_s=120)
        except Exception as error:
            record["private_diagnostic_error"] = repr(error)
    if support_reference is not None:
        # This metrology happens after the public receipt is fixed. Its truth
        # label never overrides held or verification and never controls setup.
        try:
            record["private_setup_hold"] = rpc.call("oracle.measure_grasp_hold", kwargs={
                "name": spec["object_symbol"], "reference": support_reference,
                "duration_s": .5}, timeout_s=120)
            record["private_true_sustained_grasp"] = record["private_setup_hold"]["truth"]["success"]
            executor.capture()
            executor._refresh(sorted(executor.scene.vocabulary))
            record["public_after_private_hold"] = public_observation(executor)
        except Exception as error:
            record["private_diagnostic_error"] = repr(error)
    record["executed_actions"] = executed_actions(record["motion_evidence"])
    record["physically_executed"] = record["executed_actions"] > 0
    return record


def run_first_attempt(executor, policy, rpc, case, condition):
    """Real setup first; neither attach an object nor retry the tested skill."""
    result = {"setup": [], "first_attempt": None, "status": "initializing"}
    result["initial_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    for spec in case.get("setup", []):
        try:
            stage = (execute_measured_offset(executor, spec) if spec["tool"] == "measured_offset"
                     else execute_stage(executor, policy, rpc, spec, spec["tool"], "setup"))
        except LookupError as error:
            result.update(status="setup_public_binding_missing", binding_error=str(error),
                          public_at_stop=public_observation(executor))
            return result
        except Exception as error:
            result.update(status="probe_error", raised_error=repr(error))
            return result
        result["setup"].append(stage)
        if stage.get("private_diagnostic_error"):
            result.update(status="probe_error", raised_error=stage["private_diagnostic_error"])
            return result
        receipt = stage["receipt"]
        if receipt.get("verification") == "execution_error" or receipt.get("error"):
            result["status"] = "setup_execution_error"
            return result
        if spec["tool"] == "measured_offset" and not receipt["waypoint_reached"]:
            result["status"] = "setup_public_offset_not_reached"
            return result
        if spec["tool"] == "grasp" and not (
                receipt.get("grasp_verified") is True and executor.held == receipt.get("object")):
            result["status"] = "setup_grasp_not_publicly_verified"
            return result
    if case["kind"] == "place" and executor.held is None:
        result["status"] = "setup_did_not_produce_verified_held_object"
        return result
    result["before_first_attempt_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    tool = case["kind"] if condition["executor"] == "current" else "vla_subtask"
    if case["kind"] == "grasp":
        tool = case.get("runtime_tool", "grasp")
    try:
        if case["kind"] == "grasp":
            action = bind_action(executor, policy, case, tool)
            evidence = {}
            with contact_probe_controls(executor, rpc, case, condition, action, evidence):
                result["first_attempt"] = execute_stage(executor, policy, rpc, case, tool,
                    "first_attempt", contact_evidence=evidence, action=action)
        else:
            result["first_attempt"] = execute_stage(executor, policy, rpc, case, tool, "first_attempt")
    except LookupError as error:
        result.update(status="first_attempt_public_binding_missing", binding_error=str(error),
                      public_at_stop=public_observation(executor))
        return result
    except Exception as error:
        result.update(status="probe_error", raised_error=repr(error))
        return result
    result["after_first_attempt_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    if result["first_attempt"].get("private_diagnostic_error"):
        result.update(status="probe_error", raised_error=result["first_attempt"]["private_diagnostic_error"])
    else:
        result["status"] = "first_attempt_recorded"
    return result


def private_frame_sync_sample(executor, rpc, case, before, reference, support, *, index, phase, chunk_index):
    """Save an existing measured frame and synchronous private labels only.

    This function performs no capture, perception refresh, robot action, hold,
    or stop. Missing views and nullable verdicts remain recorded. Its private
    contact sample is an instant, never a later sustained-hold label.
    """
    import numpy as np
    from robots.libero.v5_state import entity_record

    state = executor.toolkit._state
    step = state.latest_step
    private_before = rpc.call("oracle.grasp_reference", kwargs={"name": case["object_symbol"]}, timeout_s=120)
    raw = executor.p.env.raw_obs()
    robot = {key: copy.deepcopy(raw[key]) for key in (
        "robot0_joint_pos", "robot0_joint_pos_cos", "robot0_joint_pos_sin", "robot0_joint_vel",
        "robot0_gripper_qpos", "robot0_gripper_qvel", "robot0_eef_pos", "robot0_eef_quat") if key in raw}
    views, points_by_view, records = (executor.scene.measurement_views.get(before.id, {}),
                                    executor.scene.measurement_clouds_by_view.get(before.id, {}), {})
    for camera in ("agentview", "wrist"):
        measured = views.get(camera)
        points = points_by_view.get(camera)
        record = {"measurement": entity_record(measured) if measured is not None else None,
                  "points": None, "missing_reason": "current_target_points_not_measured" if points is None else None}
        if points is not None:
            cloud = np.asarray(points["xyz_world"])
            filename = f"private_frame_sync_{index:04d}_{camera}_{before.id}.npz"
            if state.save(filename, cloud, step=step) is None:
                raise RuntimeError("could not persist private-frame-sync measured cloud")
            path = state.artifact_path(filename, step=step)
            record["points"] = {key: copy.deepcopy(value) for key, value in points.items() if key != "xyz_world"}
            record["points"].update(path=str(path), sha256=sha(path), shape=list(cloud.shape),
                dtype=cloud.dtype.str, current=bool(points.get("source_step") == step
                    and points.get("object_id") == before.id and points.get("src") == "perception"),
                point_array_sha256=hashlib.sha256(cloud.tobytes(order="C")).hexdigest())
        records[camera] = record
    public_frame = (executor.independent_grasp_frame(before, support["height_m"] if support else None)
                    if getattr(executor, "grasp_independent_views_v1", False) else None)
    private_after = rpc.call("oracle.grasp_reference", kwargs={"name": case["object_symbol"]}, timeout_s=120)
    clearance = private_after["lower_extent_m"] - reference["lower_extent_m"]
    touching_support = sorted(set(reference["other_contact_geoms"]) & set(private_after["other_contact_geoms"]))
    sample = {"version": "original-private-frame-sync/1", "sample_index": index,
              "phase": phase, "chunk_index": chunk_index, "source_step": step,
              "capture_id": f"{case['name']}:step{step}:sample{index}",
              "per_view": records, "robot_observation": robot,
              "raw_robot_eef_xyz": list(map(float, executor.p._last_obs_eef_pos)),
              "raw_robot_gripper_opening": float(executor.p._last_obs_gripper),
              "frame": public_frame, "private_contact_before_read": private_before,
              "private_contact": private_after, "sim_time": private_after["sim_time"],
              "same_physics_time": private_before["sim_time"] == private_after["sim_time"],
              "private_clearance_m": clearance, "touching_original_support_geoms": touching_support,
              "private_contact_clear_instant": bool(clearance >= .03 and private_after["finger_contact"]
                                                    and not touching_support),
              "private_label_scope": "same-frame contact/clearance instant; not sustained hold or runtime control",
              "new_robot_actions": 0}
    filename = f"private_frame_sync_{index:04d}.json"
    if state.save(filename, sample, step=step) is None:
        raise RuntimeError("could not persist private-frame-sync metadata")
    path = state.artifact_path(filename, step=step)
    sample["metadata"] = {"path": str(path), "sha256": sha(path)}
    return sample


@contextmanager
def contact_probe_controls(executor, rpc, case, condition, action, evidence):
    """Scope exploration controls to this one original first attempt."""
    from scripts.probe_v5_grasp449_20261005 import (
        measured_at_gripper, measured_handle_approach, rpent_pick_then_stable_measure,
    )
    from robots.libero.v5_state import entity_record

    obj = executor.scene.entities[action.object]
    original_stage, original_vla = executor.stage_grasp, executor.vla_act
    original_execute, original_chunk = executor._execute, executor.p._vlm_chunk
    private_sync = bool(condition.get("private_frame_sync", False))
    placement_rgbd = bool(condition.get("placement_rgbd_evidence", False))
    original_refresh = executor.scene.refresh if private_sync or placement_rgbd else None
    placement_objects = {"object": obj}
    if placement_rgbd:
        if action.target is None or not executor.scene.record_sam_masks_v6:
            raise ValueError("placement RGB-D evidence needs a selected target and recorded SAM masks")
        placement_objects["target"] = executor.scene.entities[action.target]
    private_reference, chunk_index = None, 0
    evidence.update(public_grasp_observations=[], contact_prompts=[], executed_vla_actions=0,
                    prompt_origin=case.get("prompt_origin"),
                    original_task_instruction_metadata=case.get("original_instruction"))
    independent_views = bool(getattr(executor, "grasp_independent_views_v1", False))
    support = None
    if independent_views and obj.name == "frypan":
        from robots.libero.v5_perception_geometry import measured_work_surface
        world = executor.toolkit._state.load("agentview_world_high.npz", step=obj.source_step)
        support = measured_work_surface(world, [obj])
        evidence["independent_visual_support"] = support

    def stage_grasp(source, pose, receipt, **kwargs):
        if condition.get("profile") == "high_short":
            standoff = condition.get("contact_standoff_m", .20)
            if condition.get("contact_approach") == "measured_handle":
                pose, method = measured_handle_approach(executor, source, standoff,
                    condition.get("contact_category_aliases", {}),
                    handle_categories=condition.get("handle_categories", ("frypan", "moka pot")))
            else:
                pose = [(source.lower[i] + source.upper[i]) / 2 for i in (0, 1)] + [source.upper[2] + standoff]
                method = "measured_bounds_centre"
            evidence["approach"] = {"source": "RGB-D measurements", "method": method,
                                    "pose": pose, "standoff_m": standoff,
                                    "measurement": entity_record(source)}
            if (pose is None and condition.get("contact_approach") == "measured_handle"
                    and condition.get("contact_approach_fallback") == "measured_bounds_centre"):
                pose = [(source.lower[i] + source.upper[i]) / 2 for i in (0, 1)] + [source.upper[2] + standoff]
                evidence["approach"].update(original_method=method, rejection="visible_handle_not_measured",
                    fallback="measured_bounds_centre", method="measured_bounds_centre", pose=pose)
            if pose is None:
                receipt.update(executed=False, verification="unmeasured", grasp_verified=None,
                               failure_reason="visible_handle_not_measured")
                return False
            kwargs["minimum_standoff_m"] = standoff
        return original_stage(source, pose, receipt, **kwargs)

    def execute(selected, receipt, card):
        if selected.tool == "vla_subtask" and condition.get("profile") == "high_short":
            if not stage_grasp(obj, list(obj.xyz), receipt):
                return
        return original_execute(selected, receipt, card)

    def chunk(*args, **kwargs):
        nonlocal chunk_index
        kwargs.setdefault("trace_callback", executor.motion_evidence.append)
        initial_index = len(executor.motion_evidence)
        result = original_chunk(*args, **kwargs)
        chunk_index += 1
        evidence["executed_vla_actions"] += executed_actions(executor.motion_evidence[initial_index:])
        if independent_views:
            if (condition["executor"] == "vla_subtask" and not evidence["public_grasp_observations"]
                    and executor.opening_may_hold(executor.p._last_obs_gripper)
                    and executor.p._last_obs_eef_pos[2] >= obj.lower[2] + .03):
                # A macro keeps its complete control sequence. This records one
                # current frame, never a two-frame verdict, lift, hold, or stop.
                executor._refresh([obj.name])
                frame = executor.independent_grasp_frame(obj, support["height_m"] if support else None)
                evidence.setdefault("independent_grasp_frame_observations", []).append(frame)
                if frame["verified"] is True:
                    evidence["public_grasp_observations"].append({
                        "version": "read_only_independent_grasp_frame_witness/1", "frame": frame,
                        "interpretation": "single_frame_witness_not_two_frame_grasp_verdict",
                        "private_at_visual_witness": rpc.call("oracle.grasp_reference",
                            kwargs={"name": case["object_symbol"]}, timeout_s=120)})
            return result
        if (not evidence["public_grasp_observations"]
                and executor.grasp_minimum_opening <= executor.p._last_obs_gripper <= .07
                and executor.p._last_obs_eef_pos[2] >= obj.lower[2] + .03):
            # Read-only visual witness: no trial lift, hold, early stop, or
            # production-verifier recovery movement is introduced here.
            executor._refresh([obj.name])
            measured = executor.scene.entities.get(obj.id)
            public_seen = bool(measured and measured.visible and measured.source_step > obj.source_step
                and measured.lower[2] - obj.lower[2] >= .03
                and measured_at_gripper(measured, executor.p._last_obs_eef_pos))
            if public_seen:
                evidence["public_grasp_observations"].append({
                    "version": "read_only_lower_rise_and_gripper_witness/1",
                    "before": entity_record(obj), "after": entity_record(measured),
                    "gripper_opening": float(executor.p._last_obs_gripper),
                    "eef_xyz": list(map(float, executor.p._last_obs_eef_pos)),
                    "private_at_visual_witness": rpc.call("oracle.grasp_reference",
                        kwargs={"name": case["object_symbol"]}, timeout_s=120)})
        return result

    def sync_existing_refresh(*args, **kwargs):
        if placement_rgbd:
            # Measure the selected stationary support in this same captured
            # frame. The executor retains its original cached destination;
            # this extra observation cannot overwrite its fixed receipt.
            names, *rest = args
            args = (list(dict.fromkeys([*names, placement_objects["target"].name])), *rest)
        result = original_refresh(*args, **kwargs)
        if private_sync:
            samples = evidence["private_frame_sync"]["samples"]
            samples.append(private_frame_sync_sample(executor, rpc, case, obj, private_reference, support,
                index=len(samples), phase="existing_scene_refresh", chunk_index=chunk_index))
        if placement_rgbd:
            save_placement_frame("existing_scene_refresh")
        return result

    def save_placement_frame(phase):
        from scripts.v5_place527_evidence import public_placement_frame
        samples = evidence["placement_rgbd"]["samples"]
        public = public_placement_frame(executor, placement_objects, len(samples), phase)
        # Predicate reads happen only after public evidence has been fixed;
        # no simulator coordinates enter the public JSON or controller.
        samples.append({"public": public, "private_label": rpc.call(
            "oracle.skill501_truth", kwargs={"spec": case}, timeout_s=120)})

    def vla_act(prompt, max_chunks, stop, source=None, **kwargs):
        evidence["contact_prompts"].append({"text": prompt, "stop": stop, "max_chunks": max_chunks})
        if condition["executor"] == "current" and condition.get("contact_stop") == "rpent_pick":
            name = condition.get("contact_category_aliases", {}).get(source.name, source.name)
            prompt = f"pick up the {name}"
            evidence["contact_prompts"][-1].update(text=prompt, origin="selected_public_category_only")
            result, primitive, measured = rpent_pick_then_stable_measure(executor, prompt, max_chunks, source,
                at_gripper=condition.get("contact_verification") != "stable_lower",
                wrist_on_rejection=condition.get("contact_verification") == "stable_lower_gripper_wrist")
            evidence.update(rpent_pick_result=primitive, stable_visual_grasp=measured)
            if independent_views:
                verified = executor.verify_grasp_measurement(source)
                result.update(grasp_verified=verified,
                              stop="grasp_verified" if verified is True else "grasp_not_verified")
                evidence["independent_visual_grasp"] = copy.deepcopy(
                    executor.last_verification_measurements["independent_grasp"])
                evidence["legacy_contact_control_retained"] = (
                    "RPent helper aperture, trial-lift and public hold controls remain unchanged; "
                    "only the final grasp verdict uses independent current views")
            return result
        return original_vla(prompt, max_chunks, stop, source, **kwargs)

    executor.stage_grasp, executor.vla_act = stage_grasp, vla_act
    executor._execute, executor.p._vlm_chunk = execute, chunk
    try:
        if private_sync:
            private_reference = rpc.call("oracle.grasp_reference",
                kwargs={"name": case["object_symbol"]}, timeout_s=120)
            evidence["private_frame_sync"] = {"version": "original-private-frame-sync/1", "enabled": True,
                "sampling_scope": "pregrasp measured cache and every existing scene.refresh return; no added capture",
                "pregrasp_reference": private_reference, "samples": [], "new_robot_actions": 0,
                "selection_calibration_only": True, "qualification_authorized": False}
            evidence["private_frame_sync"]["samples"].append(private_frame_sync_sample(
                executor, rpc, case, obj, private_reference, support, index=0, phase="pregrasp", chunk_index=0))
        if placement_rgbd:
            evidence["placement_rgbd"] = {"version": "original-placement-rgbd/1-dev", "samples": [],
                "scope": "current object and stationary target on existing capture steps; target SAM query added",
                "new_robot_actions": 0, "qualification_authorized": False}
            save_placement_frame("pregrasp")
        if private_sync or placement_rgbd:
            executor.scene.refresh = sync_existing_refresh
        yield
    finally:
        executor.stage_grasp, executor.vla_act = original_stage, original_vla
        executor._execute, executor.p._vlm_chunk = original_execute, original_chunk
        if private_sync or placement_rgbd:
            executor.scene.refresh = original_refresh


def run_full_subtask(executor, policy, rpc, case, condition):
    """Measure the grasp phase and transfer outcome without a grasp early stop."""
    from robots.libero.v5_state import Candidate
    result = {"setup": [], "first_attempt": None, "status": "initializing"}
    result["initial_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    try:
        macro = bind_action(executor, policy, case, "vla_subtask")
    except LookupError as error:
        result.update(status="first_attempt_public_binding_missing", binding_error=str(error),
                      public_at_stop=public_observation(executor))
        return result
    action = (macro if condition["executor"] == "vla_subtask" else
              Candidate("grasp", macro.object, mode=condition.get("mode", "direct")))
    evidence = {}
    rpc.call("oracle.skill501_grasp_trace_begin", kwargs={"name": case["object_symbol"]}, timeout_s=120)
    try:
        with contact_probe_controls(executor, rpc, case, condition, action, evidence):
            result["first_attempt"] = execute_stage(executor, policy, rpc, case, action.tool,
                "first_attempt", contact_evidence=evidence, action=action)
            if result["first_attempt"].get("private_diagnostic_error"):
                result.update(status="probe_error", raised_error=result["first_attempt"]["private_diagnostic_error"])
    except Exception as error:
        result.update(status="probe_error", raised_error=repr(error), contact_evidence=evidence)
    finally:
        try:
            result["private_grasp_phase"] = rpc.call("oracle.skill501_grasp_trace_finish", timeout_s=120)
        except Exception as error:
            result.update(status="probe_error", raised_error=repr(error))
    result["after_first_attempt_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    result["private_original_task_status"] = rpc.call("oracle.status", timeout_s=120)
    if not result.get("raised_error"):
        result["status"] = "first_attempt_recorded"
    return result


def run_registered_skill(executor, policy, rpc, case, condition):
    """Reverse fixture probes are not stopped by the original task's latch."""
    with executor.p.env.complete_skill():
        runner = run_full_subtask if case["kind"] == "grasp_then_subtask" else run_first_attempt
        result = runner(executor, policy, rpc, case, condition)
        result["native_original_success_latched"] = bool(executor.p.env._native_terminated)
        result["external_action_budget_exhausted"] = bool(executor.p.env.truncated)
        result["diagnostic_native_stop_scope"] = "complete_registered_setup_and_first_skill; no harness behavior change"
        return result


def run_case(case, condition, base, endpoints, output):
    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_oracle_policy import OriginalOraclePolicy
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category, scene_vocabulary
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    cfg = {**base, **condition.get("overrides", {}), **case["episode"],
           "max_chunks": condition["max_chunks"], "motion_trace_v1": True}
    events = NullDashboardEventSink()
    port = pick_free_port()
    endpoint = f"http://127.0.0.1:{port}"
    daemon = ProcessDaemon(name="skill501_original", cmd=[sys.executable, "-m", PROBE_MODULE, "--serve",
        "--suite", cfg["suite"], "--task", str(cfg["task"]), "--seed", str(cfg["seed"]),
        "--max-episode-steps", str(cfg.get("max_episode_steps", 10000)), "--port", str(port)],
        log_path=str(output / "oracle_env.log"))
    toolkit, daemons = None, []
    try:
        daemon.start()
        rpc = HttpRpcClient(endpoint)
        wait_for_ready(rpc, daemon=daemon, timeout_s=300)
        runtime_args = argparse.Namespace(**case["episode"], libero_type="standard",
            max_episode_steps=cfg.get("max_episode_steps", 10000), env_endpoint=endpoint,
            env_client_class=V5SkillEnvClient, sam3_endpoint=endpoints["sam3"],
            vla_endpoint=endpoints["vla"], molmo_endpoint=None, cuda_device=None,
            planner="typed_choice", collect_flywheel_data=False)
        daemons, runtime = _init_runtime(runtime_args, output, events, None)
        toolkit = LiberoToolkit(runtime_kwargs=runtime, dashboard_events=events,
                               memory=MemoryManager(output / "empty_memory", memory_access="read_only"),
                               state_output_dir=output)
        scene_flags = {name: cfg[name] for name in inspect.signature(MeasuredScene).parameters
                       if name in cfg and name not in {"toolkit", "rpc", "seed"}}
        scene = MeasuredScene(toolkit, HttpRpcClient(endpoints["sam3"]), cfg["seed"], **scene_flags)
        executor_flags = {name: cfg[name] for name in inspect.signature(V5Executor).parameters
                          if name in cfg and name not in {"toolkit", "scene", "max_chunks", "instruction"}}
        executor = V5Executor(toolkit, scene, cfg["max_chunks"], **executor_flags)
        initial = toolkit.execute_tool("view_env_state", {}).result
        executor.instruction = scene.instruction = initial["task_language"]
        vocab = scene_vocabulary(initial["state"]["object_names"], executor.instruction)
        scene.instance_limits = Counter(category(name) for name in initial["state"]["object_names"])
        scene.refresh(vocab)
        policy = OriginalOraclePolicy(rpc)
        return run_registered_skill(executor, policy, rpc, case, condition)
    finally:
        if toolkit is not None:
            toolkit.close()
        for owned in reversed(daemons):
            owned.stop()
        daemon.stop()


def validate_manifest(plan):
    cases = plan["cases"]
    if len({case["name"] for case in cases}) != len(cases):
        raise ValueError("duplicate registered trial")
    for condition in plan["conditions"].values():
        if condition["executor"] not in {"current", "vla_subtask"} or condition["max_chunks"] <= 0:
            raise ValueError("registered executor or budget is invalid")
    for case in cases:
        if (case["episode"]["suite"] not in ORIGINAL_SUITES
                or case["kind"] not in {"grasp", "articulate", "place", "grasp_then_subtask"}
                or case["condition"] not in plan["conditions"]):
            raise ValueError("only explicitly registered original skill trials")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", case["name"]):
            raise ValueError("registered case name must be a single neutral directory name")
        if not re.fullmatch(r"[0-9a-f]{64}", case["state_sha256"]):
            raise ValueError("registered official state SHA is required")
        allowed = ({"direct", "above_10cm", "yaw_90"} if case["kind"] == "grasp" else
                   {"on", "in"} if case["kind"] in {"place", "grasp_then_subtask"} else
                   {"open", "close", "turn_on", "turn_off"})
        if case["mode"] not in allowed:
            raise ValueError("skill/mode mismatch")
        if case["kind"] == "grasp" and plan["conditions"][case["condition"]]["executor"] != "current":
            raise ValueError("a standalone grasp probe must use the runtime grasp executor")
        if case["kind"] == "grasp" and case.get("runtime_tool", "grasp") not in {"grasp", "regrasp_restage"}:
            raise ValueError("standalone grasp must use grasp or regrasp_restage")
        if any(step["tool"] not in {"grasp", "articulate", "retreat", "measured_offset"} for step in case.get("setup", [])):
            raise ValueError("setup must use real measured grasp, articulation or public robot motion")
        for step in case.get("setup", []):
            if step["tool"] == "measured_offset" and (
                    len(step["offset_m"]) != 3 or step["gripper"] not in {-1, 0, 1}):
                raise ValueError("measured offset requires XYZ and a public gripper command")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("shard-index must be in [0, shards)")
    plan = json.loads(args.manifest.read_text())
    validate_manifest(plan)
    config = Path(plan["base_config"]["path"])
    if sha(config) != plan["base_config"]["sha256"]:
        raise ValueError("registered original base config changed")
    base = json.loads(config.read_text())
    if base["libero_type"] != "standard" or os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("original standard LIBERO only")
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from rlinf.envs.libero.utils import benchmark
    import numpy as np

    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints = [], {}
    try:
        for name, module, extra in (("sam3", "robots.libero.v5_sam3_server", []),
                                  ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"])):
            port = pick_free_port()
            daemon = ProcessDaemon(name="skill501_" + name,
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
                    if sha(case[field]["path"]) != case[field]["sha256"]:
                        raise ValueError("registered original asset changed: " + field)
                suite = benchmark.get_benchmark(case["episode"]["suite"])()
                state = suite.get_task_init_states(case["episode"]["task"])[case["episode"]["seed"]]
                digest = hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()
                if digest != case["state_sha256"]:
                    raise ValueError("registered official initial state changed")
                output = args.output / case["name"]
                output.mkdir()
                row = {"case": case, "output_dir": str(output), "new_training_rows": 0}
                started = time.perf_counter()
                try:
                    row.update(run_case(case, plan["conditions"][case["condition"]], base, endpoints, output))
                except Exception as error:
                    row.update(status="probe_error", raised_error=repr(error))
                row["wall_s"] = time.perf_counter() - started
                trace = output / "choices.jsonl"
                stages = [*row.get("setup", []), *([row["first_attempt"]] if row.get("first_attempt") else [])]
                trace.write_text("".join(diagnostic_json(stage) + "\n" for stage in stages))
                row["choices_sha256"] = sha(trace)
                (output / "private_skill_diagnostic.json").write_text(diagnostic_json(row, indent=2) + "\n")
                ledger.write(diagnostic_json(row) + "\n")
                ledger.flush()
                print(diagnostic_json({"case": case["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
                if row.get("raised_error"):
                    raise RuntimeError("preserved development probe error; repair before further cases")
    finally:
        for daemon in reversed(daemons):
            daemon.stop()


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
