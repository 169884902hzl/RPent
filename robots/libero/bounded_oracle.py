"""Private original-task upper-bound selector for existing public skill IDs.

This module must never be imported by a model-facing adapter or serializer.
It does not create coordinates: all target poses remain public candidates.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_oracle_policy import OriginalOraclePolicy, goal_clause


class NoPublicOption(ValueError):
    """The public package has no remaining measured recovery/goal option."""


class BoundedOracle:
    def __init__(self, rpc, adapter):
        self.rpc, self.adapter = rpc, adapter
        self.binding = OriginalOraclePolicy(rpc)
        self.private_trace: list[dict] = []

    def choose(self, request):
        status = self.rpc.call("oracle.status")
        ex = self.adapter
        # Cached public anchors remain available to the selector, just as to
        # the model. Do not lose a measured stationary target merely because
        # the grasped object now occludes it. Cache age stays in the request.
        public_ids = {anchor['id'] for anchor in request['anchors']}
        entities = [replace(entity, visible=True) for entity in ex.scene.entities.values()
                    if entity.id in public_ids]
        candidates = [c for c in request["candidates"] if c["skill"] != "call_vla"]
        feasible = [c for c in candidates if c["consequences"]["collision"] is not True
                    and c["consequences"]["ik_reachable"] is not False]
        def find(skill, **parameters):
            return next((c for c in feasible if c["skill"] == skill
                and all(c["parameters"].get(key) == value for key, value in parameters.items())), None)
        def nudge(axis, direction):
            # A 2 cm sweep can be blocked while the measured 1 cm sweep
            # still permits progress. Reobserve after that smaller action;
            # do not replace it with a scan or bypass either route screen.
            return next((candidate for distance in (.02, .01)
                if (candidate := find("nudge", axis=axis,
                    distance_m=float(distance*np.sign(direction)))) is not None), None)
        chosen = None
        if status["done"]:
            chosen = find("finish")
        for goal, satisfied in zip(status["goals"], status["satisfied"]):
            if chosen or satisfied:
                continue
            predicate, symbol = goal[:2]
            phrase = goal_clause(ex.ex.instruction, symbol)
            source = self.binding.bind(symbol, entities, phrase, ex.scene.view_axes)
            target = self.binding.bind(goal[2], entities, phrase, ex.scene.view_axes, source_reference=False) if len(goal) == 3 else None
            if source is not None and predicate in {'open', 'close'} and source.id not in ex.plans:
                # A public segmented panel can expose push contact when its
                # parent's handle is not visible. Select its existing public
                # option; never create a task pose from the private goal.
                panels = [e for e in entities if e.part_of == source.id
                    and ex.plans.get(e.id, {}).get('contact_kind') == 'surface']
                if len(panels) == 1:
                    source = panels[0]
            if ex.held is not None and target is not None:
                # Use the same public pre-grasp target as the candidate route
                # and serialized anchor, rather than its now-occluded mask.
                target = ex.target_cache.get(target.id, target)
            # OriginalOraclePolicy.choose normally retains these identities.
            # This selector calls bind directly and must retain them too:
            # reinterpreting "between" after approach/occlusion loses a
            # previously resolved source even when its public ID still exists.
            for label, entity in ((symbol, source), (goal[2] if len(goal) == 3 else None, target)):
                if entity is not None:
                    self.binding._bindings[label] = entity.id
                    self.binding._binding_peers.setdefault(label, {e.id for e in entities
                        if e.id != entity.id and e.name == entity.name})
            self.private_trace.append({"goal": goal, "source_public_id": source.id if source else None,
                                       "target_public_id": target.id if target else None})
            if source is None:
                chosen = find("observe", mode="wrist_scan") or find("observe", mode="refresh")
                continue
            if len(goal) == 3 and target is None:
                # Losing a measured destination does not turn a relational
                # task into a pick. Reobserve rather than lifting a plate
                # being pushed merely because the stove was occluded.
                chosen = find("observe", mode="wrist_scan") or find("observe", mode="refresh")
                continue
            robot = request["robot"]
            xyz = np.array(robot["eef_xyz_m"])
            if ex.held == source.id and target is not None:
                object_pose = ex.scene.entities.get(source.id, source)
                inside = predicate == 'in' and all(target.lower[i] <= object_pose.lower[i]
                    and object_pose.upper[i] <= target.upper[i] for i in (0, 1))
                if not inside and np.linalg.norm((np.array(object_pose.xyz)-target.xyz)[:2]) > .025:
                    chosen = find("carry_to", target_id=target.id)
                elif object_pose.lower[2] > target.upper[2]+.025:
                    chosen = find("lower", target_id=target.id)
                    # A blocked lowering route does not remove the existing
                    # release option. For On, a centred payload at most one
                    # bounded lift above its measured support can settle by
                    # gravity. This is private option selection only: neither
                    # the public collision screen nor a task label is changed.
                    if (chosen is None and predicate == 'on'
                            and object_pose.lower[2]-target.upper[2] <= .10):
                        chosen = find("release")
                        if chosen is not None:
                            self.private_trace[-1]['recovery'] = 'release_over_measured_support_after_blocked_lower'
                else:
                    chosen = find("release")
                continue
            contact = ex.plans.get(source.id)
            if contact is None:
                chosen = find("observe", mode="wrist_scan")
                continue
            if robot["gripper_opening_m"] < .075:
                if ex.active != source.id:
                    chosen = find("set_gripper", mode="open")
                elif ex.ex.instruction.lower().startswith('push ') and target is not None:
                    delta = np.asarray(target.xyz)-source.xyz
                    axis = int(np.argmax(np.abs(delta[:2])))
                    chosen = nudge('xy'[axis], delta[axis])
                elif predicate in {"on", "in"}:
                    last = ex.receipts[-1] if ex.receipts else None
                    failed_lift = last and last['skill'] == 'lift' and last['outcome'] != 'success'
                    chosen = (None if failed_lift else find("lift", anchor_id=source.id)) or find("set_gripper", mode="open")
                elif predicate in {"turnon", "turnoff", "turn_on", "turn_off"}:
                    chosen = find("rotate_wrist", angle_deg=45 if "on" in predicate else -45)
                else:
                    normal = contact.get('surface_measurement', {}).get('normal_xyz')
                    if normal is None:
                        normal = contact.get("handle_measurement", {}).get("pose", {}).get("approach_normal_xyz", [0., -1., 0.])
                    axis = int(np.argmax(np.abs(normal)))
                    direction = (1 if predicate == "open" else -1)*np.sign(normal[axis])
                    chosen = nudge("xyz"[axis], direction)
                    # A blocked contact route needs a new contact, not an
                    # occluded scan with the same closed fingers. Opening
                    # is an existing public option and clears the adapter's
                    # contact commitment before measuring a fresh approach.
                    chosen = chosen or find("set_gripper", mode="open")
                continue
            error = np.linalg.norm(xyz-contact["xyz_m"])
            angular = (Rotation.from_quat(robot["eef_quat_xyzw"])*Rotation.from_quat(contact["quat_xyzw"]).inv()).magnitude()
            if error < .02 and angular < .2:
                chosen = find("set_gripper", mode="close")
            elif (np.linalg.norm(xyz-contact['approach_xyz_m']) < .025 if contact.get('approach_xyz_m')
                  else np.linalg.norm((xyz-contact["xyz_m"])[:2]) < .03 and xyz[2] >= contact["xyz_m"][2]):
                chosen = find("align" if angular > .05 else "descend", anchor_id=source.id)
            else:
                chosen = (find("move_to", anchor_id=source.id, approach=contact.get('preferred_approach', 'above'),
                               path=contact.get('preferred_path', 'over'))
                          or find("move_to", anchor_id=source.id, approach="front", path="direct")
                          or find("move_to", anchor_id=source.id))
        chosen = chosen or find("observe", mode="wrist_scan") or find("observe", mode="refresh")
        if chosen is None:
            raise NoPublicOption("upper-bound selector has no remaining public option")
        ids = [chosen["id"]]
        if request["max_actions"] == 4 and chosen["skill"] == "move_to":
            anchor = chosen["parameters"]["anchor_id"]
            align = find("align", anchor_id=anchor)
            descend = find("descend", anchor_id=anchor)
            ids.extend(c["id"] for c in (align, descend) if c is not None)
        return {"schema_version": request["schema_version"], "kind": "decision", "revision": request["revision"],
                "observation_id": request["observation_id"], "candidate_ids": ids}
