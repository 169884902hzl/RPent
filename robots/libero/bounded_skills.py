"""Measured LIBERO adapter for the shared bounded-skills contract.

No BDDL, oracle RPC or simulator object poses are read here. Candidate geometry
comes from dual-view RGB-D and public robot sensors. Category-specific logic
is confined to the existing grasp-region perception code.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_motion import MotionConfig, SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import remove_visual_robot
from robots.libero.v5_geometric_grasp import _opposition, panda_geometry, remove_measured_hand, side_site_rotation
from robots.libero.v5_grasp_geometry import measured_grasp_regions
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import separate_target_points
from robots.libero.v5_state import fixture_actions
from robots.libero.v5_subtasks import measured_instance_description, subtask_phrase
from rpent.skill_package import VERSION
from rpent.skill_package.contract import BOUNDARIES, FailureMemory, identity, selected, validate
from rpent.skill_package.vla import DevelopmentHistory, VLABudget, run_fallback

MOTION_SKILLS = {"move_to", "align", "descend", "lift", "carry_to", "lower", "rotate_wrist", "nudge"}


class MeasuredSkillAdapter:
    """Enumerate public options and execute only exact selected IDs."""

    def __init__(self, executor, gripper_xml: str | Path, *, allow_vla: bool = True,
                 history: DevelopmentHistory | None = None, motion_config: MotionConfig = MotionConfig()):
        self.ex, self.p, self.scene = executor, executor.p, executor.scene
        self.xml = Path(gripper_xml)
        self.geometry = panda_geometry(self.xml)
        self.robot_xml = self.xml.parent.parent/"robots/panda/robot.xml"
        self.allow_vla, self.history = allow_vla, history or DevelopmentHistory()
        self.config = motion_config
        self.memory = FailureMemory()
        self.revision = 0
        self.receipts: list[dict] = []
        self.details: list[dict] = []
        self.held: str | None = None
        self.active: str | None = None
        self.grasp_reference = None
        self.target_cache: dict = {}
        self.plans: dict = {}
        self.latest_request: dict | None = None
        self.preparation = measured_robot(self.p)
        self.gripper_command = -1. if self.preparation["gripper_opening_m"] >= .075 else 1.
        self.previous_scene = {}
        self._base_geometry = None
        self._screen_cache = {}

    def robot(self):
        state = measured_robot(self.p)
        return {key: state[key] for key in ("eef_xyz_m", "eef_quat_xyzw", "gripper_opening_m")} | {
            "held_anchor_id": self.held, "velocity_m_s": [0., 0., 0.]}

    def refresh(self):
        self.ex.capture()
        self.scene.refresh(sorted(self.scene.vocabulary))
        self._base_geometry = None
        self._screen_cache.clear()
        current = {e.id: np.array(e.xyz) for e in self.scene.entities.values() if e.visible}
        changed = any(key not in self.previous_scene or np.linalg.norm(value-self.previous_scene[key]) > .01
                      for key, value in current.items())
        self.memory.tick(scene_changed=changed)
        self.previous_scene = current
        for e in self.scene.entities.values():
            # Cache targets before a held object can obscure them. A moving
            # entity is refreshed by perception; cache age remains explicit.
            if e.visible and e.id != self.held:
                self.target_cache[e.id] = e

    def _evidence(self, entity):
        return {"measurement_id": f"rgbd:{entity.source_step}:{entity.id}",
                "capture_step": int(entity.source_step), "source": "rgbd",
                "cameras": ["main", "wrist"] if self.scene.dual_view_fusion_v1 else ["main"],
                "operation": entity.geometry or "segmented_rgbd_bounds"}

    def anchors(self):
        return [{"id": e.id, "label": e.name, "frame": "world",
                 "xyz_m": list(e.xyz), "size_m": (np.array(e.upper)-e.lower).tolist(),
                 "quat_xyzw": None, "confidence": float(self.scene._scores.get(e.id, 0.)),
                 "cached": not e.visible or bool(e.geometry and e.geometry.startswith("cached_perception")),
                 "evidence": [self._evidence(e)]}
                for e in self.scene.entities.values()
                if e.visible or (e.geometry and e.geometry.startswith("cached_perception"))]

    def _cloud_and_ik(self, anchor_id=None, *, contact=False):
        cache_key = (anchor_id, contact, self.held, tuple(measured_robot(self.p)["eef_xyz_m"]))
        if cache_key in self._screen_cache:
            return self._screen_cache[cache_key]
        robot = measured_robot(self.p)
        if self._base_geometry is None:
            from robots.libero.v5_geometric_grasp import _voxel
            clouds = [np.asarray(self.ex.toolkit._state.load(name+"_world_high.npz")).reshape(-1, 3)
                      for name in ("agentview", "wrist")]
            cloud = _voxel(np.concatenate(clouds))
            scene, _ = remove_measured_hand(cloud, robot["eef_xyz_m"], robot["eef_quat_xyzw"],
                                           self.geometry, robot["gripper_opening_m"])
            ik = PublicPoseScreen(self.robot_xml, robot["joint_positions_rad"], robot["eef_xyz_m"],
                                 robot["eef_quat_xyzw"], self.geometry["site_offset_in_gripper_m"], warm_start=True)
            scene, _ = ik.remove_measured_arm(scene)
            scene, _ = remove_visual_robot(scene, ik)
            self._base_geometry = scene, ik
        scene, ik = self._base_geometry
        target = self.scene.measurement_clouds.get(anchor_id, np.empty((0, 3)))
        if len(target):
            target, scene = separate_target_points(target, scene)
        payload = []
        if self.held:
            held_cloud = self.scene.measurement_clouds.get(self.held)
            if held_cloud is not None:
                held_cloud, scene = separate_target_points(held_cloud, scene)
                payload = (held_cloud-robot["eef_xyz_m"])@Rotation.from_quat(robot["eef_quat_xyzw"]).as_matrix()
        screen = PublicRouteScreen(scene, self.geometry, ik, opening=robot["gripper_opening_m"],
            contact_points=target, contact_allowed=contact, payload_local=payload)
        self._screen_cache[cache_key] = screen
        return screen

    def grasp_geometry(self, entity):
        """Shared opposition sampling; object-specific segmentation stays upstream."""
        points = self.scene.measurement_clouds.get(entity.id)
        if points is None or len(points) < 40:
            return None
        region, evidence = measured_grasp_regions(points, entity.name)
        if region is None:
            return None
        pads = [b for b in self.geometry["boxes"] if b["name"].endswith("_pad")]
        pad_centre = np.mean([(np.asarray(b["lower"])+b["upper"])/2 for b in pads], axis=0)
        options = []
        for seed in region["seeds"]:
            for offset in (0., math.pi/4, -math.pi/4, math.pi/2):
                angle = math.atan2(*region["closing_axis_xy"][::-1])+offset
                closing = np.array([math.cos(angle), math.sin(angle), 0.])
                centre, fit = _opposition(region["points"], seed, closing)
                if centre is None:
                    continue
                site = side_site_rotation(closing, [0., 0., -1.])
                body = site@Rotation.from_euler("z", math.pi/2).as_matrix()
                options.append({"xyz_m": (centre-site@pad_centre).tolist(),
                    "quat_xyzw": Rotation.from_matrix(body).as_quat().tolist(),
                    "width_m": fit["width_m"], "quality": fit["antipodal_quality"],
                    "perception": evidence, "fit": fit})
        return max(options, key=lambda x: x["quality"], default=None)

    def _route(self, skill, parameters, *, robot=None):
        robot = robot or measured_robot(self.p)
        start = np.array(robot["eef_xyz_m"])
        quat = robot["eef_quat_xyzw"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        entity = self.scene.entities.get(key)
        if entity is None or not entity.visible:
            entity = self.target_cache.get(key)
        point = start.copy()
        if skill in {"move_to", "align", "descend"}:
            contact = self.plans.get(key)
            if contact is None:
                return None
            goal = np.array(contact["xyz_m"])
            approach = parameters.get("approach", "above")
            right, front = map(np.asarray, self.scene.view_axes)
            direction = {"above": np.array([0., 0., 1.]), "front": front,
                         "left": -right, "right": right}[approach]
            if skill == "align":
                return [{"xyz_m": start.tolist(), "quat_xyzw": contact["quat_xyzw"]}]
            if skill == "descend":
                return [{"xyz_m": goal.tolist(), "quat_xyzw": contact["quat_xyzw"]}]
            point = goal+direction*.12
            quat = contact["quat_xyzw"]
            path = parameters["path"]
            if path == "over":
                height = max(start[2], point[2])+ .08
                return [{"xyz_m": [*start[:2], height], "quat_xyzw": robot["eef_quat_xyzw"]},
                        {"xyz_m": [*point[:2], height], "quat_xyzw": quat},
                        {"xyz_m": point.tolist(), "quat_xyzw": quat}]
            if path == "around":
                middle = (start+point)/2+right*.12
                middle[2] = max(start[2], point[2])
                return [{"xyz_m": middle.tolist(), "quat_xyzw": robot["eef_quat_xyzw"]},
                        {"xyz_m": point.tolist(), "quat_xyzw": quat}]
        elif skill == "lift":
            point[2] += .10
        elif skill in {"carry_to", "lower"}:
            if entity is None or self.held is None:
                return None
            held = self.scene.entities.get(self.held)
            if held is None:
                return None
            offset = start-np.asarray(held.xyz)
            point = np.asarray(entity.xyz)+offset
            if skill == "carry_to":
                point[2] = entity.upper[2]+max(.12, start[2]-held.lower[2])
            else:
                point[2] = entity.upper[2]+(start[2]-held.lower[2])+.012
        elif skill == "nudge":
            point["xyz".index(parameters["axis"])] += parameters["distance_m"]
        elif skill == "rotate_wrist":
            quat = (Rotation.from_quat(quat)*Rotation.from_euler("z", parameters["angle_deg"], degrees=True)).as_quat().tolist()
        return [{"xyz_m": point.tolist(), "quat_xyzw": quat}]

    def _candidate(self, skill, parameters, *, screen_options=True):
        cid = hashlib.sha256(identity({"skill": skill, "parameters": parameters}).encode()).hexdigest()[:16]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        entity = self.scene.entities.get(key)
        consequence = {"path_min_clearance_m": None, "collision": None, "ik_reachable": None,
                       "expected_width_m": self.plans.get(key, {}).get("width_m"),
                       "expected_gripper_opening_m": None, "expected_steps": 0,
                       "screen_scope": "nonmotion", "evidence_ids": [self._evidence(entity)["measurement_id"]] if entity else []}
        if skill in MOTION_SKILLS:
            route = self._route(skill, parameters)
            if route is None:
                return None
            contact = skill in {"descend", "lower", "nudge"} or (skill == "rotate_wrist" and self.active is not None)
            motion = SmoothMotion(self.p, self._cloud_and_ik(key, contact=contact), self.config)
            trajectory, _, _, evidence = motion.prepare(route)
            consequence.update({field: evidence[field] for field in ("path_min_clearance_m", "collision", "ik_reachable")})
            consequence["screen_scope"] = "contact_selected_surface" if contact else "hand_mesh_observed_space"
            consequence["expected_steps"] = math.ceil(trajectory.duration*self.config.hz)
        elif skill in {"release", "set_gripper"}:
            consequence.update(expected_steps=15, expected_gripper_opening_m=(.08 if skill == "release" or parameters.get("mode") == "open" else 0.))
        history = None
        if skill == "call_vla":
            estimate = self.history.estimate(parameters["mode"], entity.name)
            history = {field: estimate[field] for field in ("success_rate", "n", "expected_steps")}
            history["source_manifest_sha256"] = self.history.manifest_sha256
            consequence["expected_steps"] = estimate["expected_steps"] or 240
            consequence["screen_scope"] = "unmeasured"
        return {"id": cid, "skill": skill, "parameters": parameters, "consequences": consequence,
                "history": history, "recent_failures": 0, "last_failure": None}

    def request(self, *, k: int = 4, screen_options: bool = True):
        if k not in {1, 4}:
            raise ValueError("supported diagnostic K values are 1 and 4")
        self.plans.clear()
        entities = [e for e in self.scene.entities.values() if e.visible]
        for entity in entities:
            if fixture_actions(entity.name):
                handle = self.scene.measure_fixture_handle_pose(entity, self.ex.instruction)
                if handle.get("pose"):
                    pose = handle["pose"]
                    normal = np.array(pose.get("approach_normal_xyz", [*pose.get("approach_normal_xy", [0, -1]), 0.]))
                    closing = np.cross(normal, [0., 0., 1.])
                    if np.linalg.norm(closing) < .01:
                        closing = np.array([1., 0., 0.])
                    site = side_site_rotation(closing, -normal)
                    self.plans[entity.id] = {"xyz_m": pose["xyz"],
                        "quat_xyzw": Rotation.from_matrix(site@Rotation.from_euler("z", math.pi/2).as_matrix()).as_quat().tolist(),
                        "width_m": None, "handle_measurement": handle}
            elif not entity.part_of and not entity.name.startswith("area ") and not entity.name.endswith("surface"):
                contact = self.grasp_geometry(entity)
                if contact is not None:
                    self.plans[entity.id] = contact
        candidates = []
        def add(skill, **parameters):
            candidate = self._candidate(skill, parameters, screen_options=screen_options)
            if candidate is not None:
                candidates.append(candidate)
        for entity in entities:
            if entity.id in self.plans and self.held is None:
                for approach in ("above", "front", "left", "right"):
                    for path in ("direct", "over", "around"):
                        add("move_to", anchor_id=entity.id, approach=approach, path=path)
                for skill in ("align", "descend", "lift"):
                    add(skill, anchor_id=entity.id)
            if self.held and entity.id != self.held:
                add("carry_to", target_id=entity.id)
                add("lower", target_id=entity.id)
            if self.allow_vla:
                for mode in fixture_actions(entity.name) or ("pick",):
                    add("call_vla", anchor_id=entity.id, mode=mode)
                if self.held and entity.id != self.held:
                    for mode in ("on", "in"):
                        add("call_vla", anchor_id=self.held, target_id=entity.id, mode=mode)
        add("set_gripper", mode="open")
        add("set_gripper", mode="close")
        if measured_robot(self.p)["gripper_opening_m"] < .075 or self.held:
            add("release")
        for angle in (-90, -45, 45, 90):
            add("rotate_wrist", angle_deg=angle, **({"anchor_id": self.active} if self.active else {}))
        for axis in "xyz":
            for distance in (-.02, -.01, .01, .02):
                add("nudge", axis=axis, distance_m=distance, **({"anchor_id": self.active} if self.active else {}))
        for mode in ("refresh", "wrist_scan"):
            add("observe", mode=mode)
        add("finish")
        add("ask_help")
        from robots.libero.v5_state import relations
        right, front = self.scene.view_axes
        public_relations = []
        for row in relations(list(self.scene.entities.values()), right_axis=right, front_axis=front):
            _, source, relation, target = row.split()
            public_relations.append({"source_id": source, "relation": relation, "target_id": target})
        request = {"schema_version": VERSION, "kind": "request", "observation_id": f"public-{self.revision}",
            "revision": self.revision, "instruction": self.ex.instruction,
            "remaining_sim_steps": self.p.env.execution_budget()["remaining_sim_steps"],
            "anchors": self.anchors(), "robot": self.robot(), "candidates": self.memory.apply(candidates),
            "receipts": self.receipts[-3:], "relations": public_relations, "max_actions": k}
        validate(request)
        self.latest_request = request
        return request

    def execute(self, request, decision):
        choices = selected(request, decision)
        if self.latest_request is not request:
            raise ValueError("request is not the adapter's current observation")
        # Each suffix is resolved from current public geometry; a contact or
        # newly measured scene change ends the chunk before any stale suffix.
        outcomes = []
        prefix = []
        for candidate in choices:
            if candidate["skill"] in BOUNDARIES or candidate["skill"] not in MOTION_SKILLS:
                break
            prefix.append(candidate)
        if len(prefix) > 1:
            outcomes.extend(self._execute_motion_group(request, prefix))
            choices = choices[len(prefix):] if all(r["outcome"] == "success" for r in outcomes) else []
        for candidate in choices:
            receipt = self._execute_one(request, candidate)
            outcomes.append(receipt)
            self.receipts.append(receipt)
            self.memory.record(candidate, receipt["outcome"], receipt["stop_reason"])
            if receipt["outcome"] != "success" or candidate["skill"] not in MOTION_SKILLS:
                break
        self.revision += 1
        return outcomes

    def _execute_motion_group(self, request, candidates):
        """Blend adjacent free motions; report each waypoint's measured passage."""
        robot = measured_robot(self.p)
        waypoints, boundaries = [], []
        for candidate in candidates:
            route = self._route(candidate["skill"], candidate["parameters"], robot=robot)
            if route is None:
                raise ValueError("chunk anchor became unmeasured")
            waypoints.extend(route)
            boundaries.append(len(waypoints)-1)
            robot = {**robot, "eef_xyz_m": route[-1]["xyz_m"], "eef_quat_xyzw": route[-1]["quat_xyzw"]}
        motion = SmoothMotion(self.p, self._cloud_and_ik(), self.config)
        result = motion.run(waypoints, gripper=self.gripper_command, blend=True)
        self.refresh()
        trace = result.get("trace", [])
        cursor, receipts = 0, []
        for candidate, boundary in zip(candidates, boundaries):
            target = np.asarray(waypoints[boundary]["xyz_m"])
            # Desired passage partitions the executed stream. It is not an
            # extra servo stop, nor a claim the actual pose hit the waypoint.
            if trace:
                candidates_i = range(cursor, len(trace))
                at = min(candidates_i, key=lambda i: np.linalg.norm(np.asarray(trace[i]["desired"]["xyz_m"])-target)) if cursor < len(trace) else len(trace)-1
                segment = trace[cursor:at+1]
                after_raw = trace[at]["after"]
                before_raw = segment[0]["before"] if segment else after_raw
                error = float(np.linalg.norm(np.asarray(after_raw["eef_xyz_m"])-target))
                cursor = at+1
                def sensor(raw):
                    return {k: raw[k] for k in ("eef_xyz_m", "eef_quat_xyzw", "gripper_opening_m")} | {
                        "held_anchor_id": self.held, "velocity_m_s": [0., 0., 0.]}
                before, after = sensor(before_raw), sensor(after_raw)
            else:
                segment, error, before, after = [], float("inf"), request["robot"], self.robot()
            outcome = "success" if error <= self.config.endpoint_tolerance_m else "failure"
            reason = "measured_waypoint_passage" if outcome == "success" else result["stop_reason"]
            receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
                "candidate_id": candidate["id"], "skill": candidate["skill"], "outcome": outcome,
                "phase": None if outcome == "success" else "planning_unreachable", "stop_reason": reason,
                "steps_used": len(segment), "before": before, "after": after, "changes": [],
                "evidence": [self._evidence(e) for e in self.scene.entities.values()]}
            validate(receipt)
            receipts.append(receipt)
            self.receipts.append(receipt)
            self.memory.record(candidate, outcome, reason)
        self.details.append({"candidate_ids": [c["id"] for c in candidates], "execution": result,
                             "blended": True, "waypoint_errors_are_measured": True})
        return receipts

    def _execute_one(self, request, candidate):
        before = self.robot()
        start_steps = self.p.env.execution_budget()["used_sim_steps"]
        entities_before = dict(self.scene.entities)
        skill, parameters = candidate["skill"], candidate["parameters"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        phase, outcome, reason, detail = None, "unmeasured", "measurement_missing", {}
        if skill in MOTION_SKILLS:
            route = self._route(skill, parameters)
            if route is None:
                phase, outcome, reason = "perception", "failure", "current_anchor_unmeasured"
            else:
                motion = SmoothMotion(self.p, self._cloud_and_ik(key, contact=skill in {"descend", "lower", "nudge"}
                    or (skill == "rotate_wrist" and self.active is not None)), self.config)
                detail = motion.run(route, gripper=self.gripper_command)
                if skill == "descend":
                    self.active = key
                    self.grasp_reference = (entities_before.get(key), np.array(self.robot()["eef_xyz_m"]))
                reason = detail["stop_reason"]
                outcome = "success" if detail.get("endpoint_error_m", 1.) <= self.config.endpoint_tolerance_m else "failure"
                phase = None if outcome == "success" else ("collision" if "collision" in reason else "planning_unreachable")
        elif skill in {"release", "set_gripper"}:
            opening = skill == "release" or parameters.get("mode") == "open"
            self.gripper_command = -1. if opening else 1.
            prior = before["gripper_opening_m"]
            for _ in range(15):
                if self.p.env.terminated or self.p.env.truncated:
                    break
                self.p._step_env(np.r_[np.zeros(6), -1. if opening else 1.])
            current = measured_robot(self.p)["gripper_opening_m"]
            outcome = "success" if abs(current-prior) >= .003 else "no_effect"
            reason = "measured_gripper_change" if outcome == "success" else "no_measured_change"
            if opening:
                self.held = None
        elif skill == "observe":
            if parameters["mode"] == "wrist_scan":
                point = np.array(before["eef_xyz_m"])+[0., 0., .04]
                detail = SmoothMotion(self.p, self._cloud_and_ik(), self.config).run([{"xyz_m": point.tolist()}], gripper=self.gripper_command)
            outcome, reason = "success", "fresh_public_views"
        elif skill == "call_vla":
            detail = self.call_vla(parameters)
            outcome, reason = detail["outcome"], detail["stop_reason"]
            phase = None if outcome == "success" else "contact_failure"
        elif skill == "finish":
            outcome = "success" if self.p.env.terminated else "rejected"
            reason = "native_success" if outcome == "success" else "environment_reports_task_incomplete"
        elif skill == "ask_help":
            outcome, reason = "rejected", "no_human_available_use_observe_restage_or_other_approach"
        self.refresh()
        if skill == "lift" and self.grasp_reference is not None:
            source, eef_at_contact = self.grasp_reference
            current = self.scene.entities.get(key)
            if source is not None and current is not None and current.visible:
                rise = current.lower[2]-source.lower[2]
                coupling = np.linalg.norm((np.array(current.xyz)-source.xyz)-(np.array(self.robot()["eef_xyz_m"])-eef_at_contact))
                opening = self.robot()["gripper_opening_m"]
                detail["public_hold"] = {"rise_m": rise, "relative_displacement_m": float(coupling), "opening_m": opening}
                if rise >= .03 and coupling <= .015 and .005 < opening < .075:
                    self.held = key
                else:
                    outcome, phase, reason = "failure", "contact_failure", "public_hold_not_verified"
            else:
                outcome, phase, reason = "unmeasured", "verification_error", "lifted_object_not_visible"
        changes = [{"anchor_id": eid,
            "displacement_m": (np.asarray(entity.xyz)-entities_before[eid].xyz).tolist() if eid in entities_before and entity.visible else None,
            "held": eid == self.held if self.held else None, "relation": None, "fixture_state": None}
            for eid, entity in self.scene.entities.items()]
        receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
            "candidate_id": candidate["id"], "skill": skill, "outcome": outcome, "phase": phase,
            "stop_reason": reason, "steps_used": self.p.env.execution_budget()["used_sim_steps"]-start_steps,
            "before": before, "after": self.robot(), "changes": changes,
            "evidence": [self._evidence(entity) for entity in self.scene.entities.values()]}
        validate(receipt)
        self.details.append({"candidate_id": candidate["id"], "execution": detail})
        self.ex.held = self.held
        return receipt

    def call_vla(self, parameters):
        if not self.allow_vla:
            raise ValueError("call_vla disabled for the oracle upper-bound diagnostic")
        source = self.scene.entities[parameters["anchor_id"]]
        mode = parameters["mode"]
        name = measured_instance_description(source, self.scene.entities, self.scene.view_axes)
        target = self.scene.entities.get(parameters.get("target_id"))
        target_name = measured_instance_description(target, self.scene.entities, self.scene.view_axes) if target else None
        prompt = f"pick up the {name}" if mode == "pick" else subtask_phrase(name, mode, target_name)
        initial = source
        initial_step = self.p.env.execution_budget()["used_sim_steps"]
        initial_endpoint = self.scene.measure_fixture_endpoint(source, name) if mode in {"open", "close"} else None
        initial_stove = self.ex.measure_stove(source) if mode in {"turn_on", "turn_off"} else None
        checks = []
        self.vla_trace = []
        hold_frames = []
        def observe():
            self.refresh()
            current = self.scene.entities.get(source.id)
            robot = self.robot()
            displacement = np.asarray(current.xyz)-initial.xyz if current and current.visible else np.full(3, np.nan)
            completed = False
            if mode == "pick" and current and current.visible:
                raised = current.lower[2]-initial.lower[2] >= .03 and .005 < robot["gripper_opening_m"] < .075
                if raised:
                    hold_frames.append((np.array(current.xyz), np.array(robot["eef_xyz_m"])))
                else:
                    hold_frames.clear()
                if len(hold_frames) >= 2:
                    obj_before, hand_before = hold_frames[-2]
                    completed = np.linalg.norm((np.array(current.xyz)-obj_before)
                        -(np.array(robot["eef_xyz_m"])-hand_before)) <= .015
            elif mode in {"open", "close"}:
                from robots.libero.v5_verification import measured_fixture_endpoint
                state = self.scene.measure_fixture_endpoint(source, name)
                verdict, _ = measured_fixture_endpoint(initial_endpoint, state, mode,
                    drawer="drawer" in source.name or "cabinet" in source.name, signed_drawer_v6=True)
                completed = verdict is True
                if state.get("moving"):
                    displacement = np.array(state["moving"]["centre"])
            elif mode in {"turn_on", "turn_off"}:
                from robots.libero.v5_stove_measurement import measured_stove_endpoint
                stove = self.ex.measure_stove(source)
                verdict, _ = measured_stove_endpoint(initial_stove, stove, mode)
                completed = verdict is True
                displacement = np.array([float(stove.get("red_fraction", 0.)), 0., 0.])
            elif target and current and current.visible:
                from robots.libero.v5_verification import strict_place_verified_v6
                elapsed = (self.p.env.execution_budget()["used_sim_steps"]-initial_step)/self.config.hz
                completed = strict_place_verified_v6(initial, current, target, robot["gripper_opening_m"],
                    robot["eef_xyz_m"], elapsed, relation=mode) is True
            distance = float(np.linalg.norm(np.asarray(robot["eef_xyz_m"])-initial.xyz))
            # Moving toward a stationary object is progress during approach.
            progress = [*displacement.tolist(), distance]
            result = {"progress_vector_m": progress, "completed": bool(completed),
                      "outside_region": distance > .6, "evidence": [self._evidence(current)] if current else []}
            checks.append(result)
            return result
        def prepare():
            route = [{"xyz_m": self.preparation["eef_xyz_m"], "quat_xyzw": self.preparation["eef_quat_xyzw"]}]
            result = SmoothMotion(self.p, self._cloud_and_ik(), self.config).run(route, gripper=self.gripper_command)
            return {**result, "success": result.get("endpoint_error_m", 1.) <= self.config.endpoint_tolerance_m}
        def predict(text):
            observation = dict(self.p._last_obs)
            observation["task_descriptions"] = text
            observation.setdefault("extra_view_images", None)
            return self.p.model.predict(observation, options={"mode": "eval"})
        def step(action):
            before = measured_robot(self.p)
            self.gripper_command = float(action[6])
            self.p._step_env(action)
            after = measured_robot(self.p)
            self.vla_trace.append({"before": before, "after": after, "action": np.asarray(action).tolist()})
            return before, after
        def handoff(trace):
            if not trace:
                return {"steps_used": 0}
            motion = SmoothMotion(self.p, self._cloud_and_ik(source.id, contact=True), self.config)
            rows = [{"time_s": i/self.config.hz, "after": row["after"]} for i, row in enumerate(trace[-4:])]
            motion._brake(rows, self.gripper_command)
            return {"steps_used": max(0, len(rows)-min(len(trace), 4)), "trace": rows}
        result = run_fallback(prompt=prompt, prepare=prepare, predict=predict, step=step, observe=observe,
            native_done=lambda: self.p.env.terminated, native_stopped=lambda: self.p.env.terminated or self.p.env.truncated,
            handoff=handoff, budget=VLABudget())
        result["template"] = {"version": "measured-libero-subtask/2-selected-instance", "mode": mode, "prompt": prompt}
        return result
