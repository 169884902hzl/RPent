# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Private original-task upper-bound selector for existing public skill IDs.

This module must never be imported by a model-facing adapter or serializer.
It does not create coordinates: all target poses remain public candidates.
"""
from __future__ import annotations

import re
import copy
import hashlib
import json
from dataclasses import replace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_oracle_policy import OriginalOraclePolicy, goal_clause
from robots.libero.bounded_chunk import PublicPrefixPrediction
from rpent.skill_package.contract import LEGALITY_VERSION, is_boundary, legal_after, validate_labels

JUDGE_VERSION = 'libero-private-task-progress-rules/10'


class NoPublicOption(ValueError):
    """The public package has no remaining measured recovery/goal option."""


class BoundedOracle:
    def __init__(self, rpc, adapter):
        self.rpc, self.adapter = rpc, adapter
        self.binding = OriginalOraclePolicy(rpc)
        self.private_trace: list[dict] = []

    def _between_pair(self, source_symbol, target_symbol, entities, phrase, axes):
        """Resolve a unique measured source/reference pair, retaining all anchors.

        An extra category detection need not make the relation ambiguous: only
        one of the measured reference instances may actually bracket a source.
        This is private option selection, not removal from public perception.
        """
        if not re.search(r"\bbetween\b", phrase, re.IGNORECASE):
            return None, None
        references = [e for e in entities if self.binding.bind(
            target_symbol, [e], "", axes, source_reference=False) is e]
        pairs = []
        for reference in references:
            alternative_ids = {e.id for e in references if e.id != reference.id}
            hypothesis = [e for e in entities if e.id not in alternative_ids]
            source = self.binding.bind(source_symbol, hypothesis, phrase, axes)
            target = self.binding.bind(target_symbol, hypothesis, phrase, axes,
                                       source_reference=False)
            if source is not None and target is not None and source.id != target.id:
                pairs.append((source, target))
        return pairs[0] if len(pairs) == 1 else (None, None)

    def _choose_one(self, request, status, *, predicted_prefix=False):
        ex = self.adapter
        # Cached public anchors remain available to the selector, just as to
        # the model. Do not lose a measured stationary target merely because
        # the grasped object now occludes it. Cache age stays in the request.
        public_ids = {anchor['id'] for anchor in request['anchors']}
        entities = [replace(entity, visible=True) for entity in ex.scene.entities.values()
                    if entity.id in public_ids]
        candidates = [c for c in request["candidates"] if c["skill"] != "call_vla"]
        feasible = [c for c in candidates if c["consequences"]["collision"] is not True
                    and c["consequences"]["ik_reachable"] is not False
                    and c["consequences"]["screen_scope"] != "conditional_on_prefix"]
        def find(skill, **parameters):
            return next((c for c in feasible if c["skill"] == skill
                and all(c["parameters"].get(key) == value for key, value in parameters.items())), None)
        def measure_contact():
            # Each executed step already refreshes and checks its receipt.
            # A speculative obstruction must end the existing prefix, not
            # spend a zero-motion observe and its recovery failure budget.
            if predicted_prefix:
                self.private_trace[-1]['await_prefix_measurement'] = True
            return find('observe', mode='refresh')
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
            if len(goal) == 3 and (source is None or target is None):
                paired_source, paired_target = self._between_pair(
                    symbol, goal[2], entities, phrase, ex.scene.view_axes)
                if paired_source is not None:
                    source, target = paired_source, paired_target
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
                object_centre = (np.asarray(object_pose.lower)+object_pose.upper)/2
                target_centre = (np.asarray(target.lower)+target.upper)/2
                if not inside and np.linalg.norm((object_centre-target_centre)[:2]) > .025:
                    chosen = (find("carry_to", target_id=target.id)
                        or find('align', anchor_id=source.id))
                    if chosen is None:
                        # A short measured lift can be clear while the full
                        # transport/scan sweep is blocked. Select only an
                        # existing screened option, then measure again; do
                        # not discard the held instance or relax the screen.
                        chosen = next((candidate for distance in (.02, .01)
                            if (candidate := find('nudge', anchor_id=source.id,
                                axis='z', distance_m=distance)) is not None), None)
                        if chosen is not None:
                            self.private_trace[-1]['recovery'] = 'screened_bounded_lift_after_blocked_transport'
                    if chosen is None:
                        # Contact can block an upward escape while a short
                        # lateral route is already screened and reachable.
                        # Use its measured progress towards the destination;
                        # the selector cannot invent or unscreen a waypoint.
                        distance = float(np.sum((object_centre-target_centre)[:2]**2))
                        lateral = []
                        for candidate in feasible:
                            parameters = candidate['parameters']
                            if (candidate['skill'] != 'nudge'
                                    or parameters.get('anchor_id') != source.id
                                    or parameters.get('axis') not in {'x', 'y'}):
                                continue
                            endpoint = object_centre.copy()
                            endpoint['xy'.index(parameters['axis'])] += parameters['distance_m']
                            remaining = float(np.sum((endpoint-target_centre)[:2]**2))
                            if remaining < distance:
                                lateral.append((remaining, candidate['id'], candidate))
                        if lateral:
                            chosen = min(lateral, key=lambda entry: entry[:2])[2]
                            self.private_trace[-1]['recovery'] = 'screened_lateral_progress_after_blocked_transport'
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
                # A failed contact can invalidate its fit while the hand
                # stays closed at that source. Reopen before reapproaching;
                # exhausting scans must not hide this existing public option.
                if (ex.active == source.id and ex.held is None
                        and request['robot']['gripper_opening_m'] < .075):
                    chosen = find('set_gripper', mode='open')
                    if chosen is not None:
                        self.private_trace[-1]['recovery'] = 'open_lost_contact_before_reapproach'
                if chosen is None and predicted_prefix:
                    chosen = measure_contact()
                if chosen is None:
                    attempted = {receipt['candidate_id'] for receipt in ex.receipts}
                    for option in feasible:
                        if (option['skill'] != 'move_to' or option['parameters']['anchor_id'] != source.id
                                or option['id'] in attempted):
                            continue
                        route = ex._route('move_to', option['parameters'], robot=robot)
                        if route is not None and np.linalg.norm(np.asarray(route[-1]['xyz_m'])-xyz) > .02:
                            chosen = option
                            self.private_trace[-1]['recovery'] = 'measured_anchor_approach_without_contact_fit'
                            break
                chosen = chosen or find("observe", mode="wrist_scan")
                continue
            if robot["gripper_opening_m"] < .075:
                if ex.active != source.id:
                    chosen = find("set_gripper", mode="open")
                elif ex.ex.instruction.lower().startswith('push ') and target is not None:
                    delta = np.asarray(target.xyz)-source.xyz
                    axis = int(np.argmax(np.abs(delta[:2])))
                    chosen = nudge('xy'[axis], delta[axis])
                    if chosen is None and predicted_prefix:
                        chosen = measure_contact()
                elif predicate in {"on", "in"}:
                    last = ex.receipts[-1] if ex.receipts else None
                    failed_lift = last and last['skill'] == 'lift' and last['outcome'] != 'success'
                    chosen = None if failed_lift else find("lift", anchor_id=source.id)
                    if chosen is None and not failed_lift:
                        # Await the prefix's actual contact measurement
                        # before discarding an unmeasured grasp.
                        chosen = measure_contact()
                    chosen = chosen or find("set_gripper", mode="open")
                elif predicate in {"turnon", "turnoff", "turn_on", "turn_off"}:
                    direction = 1 if "on" in predicate else -1
                    normal = contact.get('handle_measurement', {}).get('pose', {}).get('approach_normal_xyz')
                    if normal is not None:
                        # rotate_wrist uses the hand's local z axis. A hand
                        # approaching from above points that axis into the
                        # measured control, reversing the outward turn sign.
                        wrist_axis = Rotation.from_quat(robot['eef_quat_xyzw']).apply([0., 0., 1.])
                        direction *= np.sign(np.dot(wrist_axis, normal))
                    chosen = find("rotate_wrist", angle_deg=float(45*direction))
                    if chosen is None:
                        chosen = (measure_contact() if predicted_prefix
                                  else find("set_gripper", mode="open"))
                else:
                    normal = contact.get('surface_measurement', {}).get('normal_xyz')
                    if normal is None:
                        normal = contact.get("handle_measurement", {}).get("pose", {}).get("approach_normal_xyz", [0., -1., 0.])
                    normal = np.asarray(normal)
                    for axis in np.argsort(-np.abs(normal), kind='stable'):
                        direction = (1 if predicate == "open" else -1)*np.sign(normal[axis])
                        option = nudge("xyz"[axis], direction)
                        # A blocked dominant axis can leave a shorter safe
                        # push on another measured normal component. Require
                        # the same 5mm progress resolution; tiny PCA noise
                        # must not turn an unrelated axis into progress.
                        if (option is not None and abs(normal[axis]
                                * option['parameters']['distance_m']) >= .005):
                            chosen = option
                            break
                    # A predicted blocked sweep is not a measured failed
                    # contact. Await the executed prefix's checks instead of
                    # closing and immediately reopening in one chunk. A
                    # measured blocked route keeps the existing recovery.
                    if chosen is None:
                        chosen = (measure_contact() if predicted_prefix
                                  else find("set_gripper", mode="open"))
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
        return chosen

    def _acceptable(self, request, status, *, predicted_prefix=False):
        """All public choices allowed by the private task-progress rules.

        Independent unsatisfied goals contribute their next safe phase. All
        screened approaches to that source and shorter same-direction contact
        increments are equivalent progress options, not measured successes.
        """
        selected = []
        goals = [(goal, done) for goal, done in zip(status['goals'], status['satisfied']) if not done]
        statuses = ([status] if status['done'] or not goals else
            [{**status, 'goals': [goal], 'satisfied': [False]} for goal, _ in goals])
        for one_goal in statuses:
            probe = copy.copy(self)
            probe.binding = copy.deepcopy(self.binding, {id(self.binding.rpc): self.binding.rpc})
            probe.private_trace = []
            try:
                selected.append(probe._choose_one(request, one_goal, predicted_prefix=predicted_prefix))
            except NoPublicOption:
                continue
        acceptable = set()
        for chosen in selected:
            acceptable.add(chosen['id'])
            params = chosen['parameters']
            for candidate in request['candidates']:
                effect = candidate['consequences']
                if (effect['collision'] is True or effect['ik_reachable'] is False
                        or effect['screen_scope'] == 'conditional_on_prefix'
                        or candidate['skill'] != chosen['skill']):
                    continue
                other = candidate['parameters']
                if chosen['skill'] == 'move_to' and other.get('anchor_id') == params['anchor_id']:
                    if params['anchor_id'] not in self.adapter.plans:
                        if candidate['id'] in {receipt['candidate_id'] for receipt in self.adapter.receipts}:
                            continue
                        route = self.adapter._route('move_to', other, robot=request['robot'])
                        if route is None or np.linalg.norm(np.asarray(route[-1]['xyz_m'])-request['robot']['eef_xyz_m']) <= .02:
                            continue
                    acceptable.add(candidate['id'])
                if (chosen['skill'] == 'nudge' and other.get('anchor_id') == params.get('anchor_id')
                        and other['axis'] == params['axis']
                        and 0 < other['distance_m']/params['distance_m'] <= 1):
                    acceptable.add(candidate['id'])
                if (chosen['skill'] == 'rotate_wrist' and other.get('anchor_id') == params.get('anchor_id')
                        and 0 < other['angle_deg']/params['angle_deg'] <= 1):
                    acceptable.add(candidate['id'])
        return acceptable

    def choose(self, request):
        status = self.rpc.call('oracle.status')
        prediction = PublicPrefixPrediction(self.adapter, request)
        virtual = copy.copy(self)
        virtual.binding = copy.deepcopy(self.binding, {id(self.binding.rpc): self.binding.rpc})
        virtual.adapter = prediction.adapter
        virtual.private_trace = []
        ids, labels = [], []
        self.last_legality_audit = {'version': LEGALITY_VERSION,
            'selected_outside_legal': 0, 'rule_acceptable_outside_legal': 0}
        for _ in range(request['max_actions']):
            legal = list(legal_after(request, ids))
            if not legal:
                break
            context = prediction.context()
            current = {**request, 'candidates': [c for c in context['candidates'] if c['id'] in legal],
                       'robot': context['predicted_robot']}
            try:
                predicted_prefix = bool(ids) or request.get('execution_prefix') is not None
                trace_start = len(virtual.private_trace)
                chosen = virtual._choose_one(current, status, predicted_prefix=predicted_prefix)
            except NoPublicOption:
                if ids:
                    break
                raise
            if ids and any(row.get('await_prefix_measurement')
                           for row in virtual.private_trace[trace_start:]):
                break
            acceptable = virtual._acceptable(current, status, predicted_prefix=predicted_prefix)
            acceptable.add(chosen['id'])
            self.last_legality_audit['selected_outside_legal'] += int(chosen['id'] not in legal)
            self.last_legality_audit['rule_acceptable_outside_legal'] += len(acceptable-set(legal))
            if chosen['id'] not in legal or not acceptable <= set(legal):
                raise ValueError('private oracle returned an option outside public legal_after')
            labels.append({'prefix': list(ids), 'legal': legal, 'selected': chosen['id'],
                'rule_acceptable': [cid for cid in legal if cid in acceptable],
                'measured_success': [], 'measured_failure': [], 'judge': JUDGE_VERSION,
                'evidence': [{'source': 'original_task_predicates_private', 'model_visible': False,
                    'initial_task_status': status,
                    'conditional_on_prefix': list(ids), 'predicted_predecessor_checks': context['assumptions'],
                    'public_legality_audit': dict(self.last_legality_audit),
                    'physically_executed_alternatives': False}]})
            ids.append(chosen['id'])
            legacy_end = (self.adapter.legacy_chunk_boundaries_v1 and (
                chosen['skill'] in {'descend', 'lower', 'lift', 'set_gripper', 'release'}
                or chosen['skill'] in {'nudge', 'rotate_wrist'} and chosen['parameters'].get('anchor_id')))
            if is_boundary(chosen) or legacy_end:
                break
            prediction.advance(chosen)
        self.private_trace.extend(virtual.private_trace)
        self.binding = virtual.binding
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.last_labels = dict(schema_version=request['schema_version'], kind='oracle_labels',
            observation_id=request['observation_id'], revision=request['revision'], request_sha256=digest, positions=labels)
        validate_labels(request, self.last_labels)
        return {'schema_version': request['schema_version'], 'kind': 'decision', 'revision': request['revision'],
                'observation_id': request['observation_id'], 'candidate_ids': ids}
