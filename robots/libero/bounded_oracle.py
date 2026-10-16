"""Private original-task upper-bound selector for existing public skill IDs.

This module must never be imported by a model-facing adapter or serializer.
It does not create coordinates: all target poses remain public candidates.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_oracle_policy import OriginalOraclePolicy, goal_clause


class BoundedOracle:
    def __init__(self, rpc, adapter):
        self.rpc, self.adapter = rpc, adapter
        self.binding = OriginalOraclePolicy(rpc)
        self.private_trace: list[dict] = []

    def choose(self, request):
        status = self.rpc.call("oracle.status")
        ex = self.adapter
        entities = list(ex.scene.entities.values())
        candidates = [c for c in request["candidates"] if c["skill"] != "call_vla"]
        feasible = [c for c in candidates if c["consequences"]["collision"] is not True
                    and c["consequences"]["ik_reachable"] is not False]
        def find(skill, **parameters):
            return next((c for c in feasible if c["skill"] == skill
                and all(c["parameters"].get(key) == value for key, value in parameters.items())), None)
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
            # OriginalOraclePolicy.choose normally retains these identities.
            # This selector calls bind directly and must retain them too:
            # reinterpreting "between" after approach/occlusion loses a
            # previously resolved source even when its public ID still exists.
            for label, entity in ((symbol, source), (goal[2] if len(goal) == 3 else None, target)):
                if entity is not None:
                    self.binding._bindings[label] = entity.id
                    self.binding._binding_peers[label] = {e.id for e in entities
                        if e.id != entity.id and e.name == entity.name}
            self.private_trace.append({"goal": goal, "source_public_id": source.id if source else None,
                                       "target_public_id": target.id if target else None})
            if source is None:
                chosen = find("observe", mode="wrist_scan") or find("observe", mode="refresh")
                continue
            robot = request["robot"]
            xyz = np.array(robot["eef_xyz_m"])
            if ex.held == source.id and target is not None:
                object_pose = ex.scene.entities.get(source.id, source)
                if np.linalg.norm((np.array(object_pose.xyz)-target.xyz)[:2]) > .025:
                    chosen = find("carry_to", target_id=target.id)
                elif object_pose.lower[2] > target.upper[2]+.025:
                    chosen = find("lower", target_id=target.id)
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
                elif predicate in {"on", "in"}:
                    chosen = find("lift", anchor_id=source.id)
                elif predicate in {"turnon", "turnoff", "turn_on", "turn_off"}:
                    chosen = find("rotate_wrist", angle_deg=45 if "on" in predicate else -45)
                else:
                    normal = contact.get("handle_measurement", {}).get("pose", {}).get("approach_normal_xyz", [0., -1., 0.])
                    axis = int(np.argmax(np.abs(normal)))
                    distance = .02*(1 if predicate == "open" else -1)*np.sign(normal[axis])
                    chosen = find("nudge", axis="xyz"[axis], distance_m=float(distance))
                continue
            error = np.linalg.norm(xyz-contact["xyz_m"])
            angular = (Rotation.from_quat(robot["eef_quat_xyzw"])*Rotation.from_quat(contact["quat_xyzw"]).inv()).magnitude()
            if error < .02 and angular < .2:
                chosen = find("set_gripper", mode="close")
            elif np.linalg.norm((xyz-contact["xyz_m"])[:2]) < .03 and xyz[2] >= contact["xyz_m"][2]:
                chosen = find("descend", anchor_id=source.id)
            else:
                chosen = (find("move_to", anchor_id=source.id, approach="above", path="over")
                          or find("move_to", anchor_id=source.id, approach="front", path="direct")
                          or find("move_to", anchor_id=source.id))
        chosen = chosen or find("observe", mode="wrist_scan") or find("observe", mode="refresh")
        if chosen is None:
            raise ValueError("upper-bound selector has no remaining public option")
        ids = [chosen["id"]]
        if request["max_actions"] == 4 and chosen["skill"] == "move_to":
            anchor = chosen["parameters"]["anchor_id"]
            align = find("align", anchor_id=anchor)
            descend = find("descend", anchor_id=anchor)
            ids.extend(c["id"] for c in (align, descend) if c is not None)
        return {"schema_version": request["schema_version"], "kind": "decision", "revision": request["revision"],
                "observation_id": request["observation_id"], "candidate_ids": ids}
