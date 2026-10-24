"""Expose exhausted route screens only while their public inputs are identical."""
import copy
import hashlib
import json

import numpy as np

from robots.libero.bounded_motion import measured_robot
from rpent.skill_package.contract import identity


def route_geometry(plan):
    """Exclude capture IDs and evidence paths from otherwise identical routes."""
    direct=('xyz_m','quat_xyzw','width_m','approach_xyz_m','approach_route','contact_route',
        'preferred_approach','preferred_path','contact_kind','move_endpoint_xyz_m')
    result={key:plan[key] for key in direct if key in plan}
    if 'surface_contact_options' in plan:
        result['surface_contact_options']={key:route_geometry(value)
            for key,value in plan['surface_contact_options'].items()}
    surface=plan.get('surface_measurement',{})
    result['surface_measurement']={key:surface[key] for key in ('xyz_world','normal_xyz') if key in surface}
    # Current RGB-D and measured clouds below bind every physical sample.
    # Handle evidence may carry new file paths on an unchanged capture;
    # its derived route and current measured surface already bind geometry.
    return result


def public_context(adapter):
    if adapter.held is not None or adapter.active is not None:
        return None
    digest = hashlib.sha256()
    digest.update(json.dumps(measured_robot(adapter.p), sort_keys=True).encode())
    # Geometry plans and the public derivative history affect the actual
    # screened route even when the instantaneous EEF pose is unchanged.
    planning = {'motion_samples': getattr(adapter.p, '_bounded_motion_samples', []),
        'rest_reference': getattr(adapter.p, '_bounded_rest_reference', None),
        'config': vars(adapter.config),'robot_geometry':adapter.geometry}
    digest.update(json.dumps(planning, sort_keys=True,
        default=lambda value: value.tolist() if hasattr(value, 'tolist') else str(value)).encode())
    # Include the actual current observations, not their capture counter. An
    # unchanged world may be captured twice, while an occluder may move without
    # changing the selected anchor's centre.
    state = adapter.ex.toolkit._state
    for camera in ('agentview', 'wrist'):
        for suffix in ('_world_high.npz', '_high.png'):
            value = np.ascontiguousarray(state.load(camera+suffix))
            digest.update(str((value.shape, value.dtype.str)).encode())
            digest.update(value.view(np.uint8))
    return digest.hexdigest()


def candidate_geometry(adapter, candidate):
    """Bind the selected route and exact screened pixels, not other detections."""
    key=candidate['parameters'].get('anchor_id')
    entity=adapter.scene.entities.get(key)
    if entity is None or not entity.visible:
        entity=adapter.target_cache.get(key,entity)
    shape=(entity.name,entity.xyz,entity.lower,entity.upper,entity.visible,entity.part_of) if entity else None
    digest=hashlib.sha256(json.dumps({'route':route_geometry(adapter.plans.get(key,{})),
        'anchor':shape},sort_keys=True,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v)).encode())
    # The candidate builder already constructs this capture's shared screen.
    # Hash its exact obstacle/target arrays; unrelated SAM association IDs do
    # not change the collision or IK inputs for this selected anchor.
    screen=adapter._cloud_and_ik(key,contact=False)
    for field in ('points','target','payload'):
        value=np.ascontiguousarray(getattr(screen,field,np.empty((0,3))))
        digest.update(field.encode());digest.update(str((value.shape,value.dtype.str)).encode())
        digest.update(value.view(np.uint8))
    return digest.hexdigest()


def remember(adapter, candidate, receipt, detail, before_context):
    """A partial physical motion cannot certify a blocked starting route."""
    screen = detail.get('screen') or {}
    if (candidate['skill'] != 'move_to' or receipt['outcome'] != 'failure' or receipt['steps_used'] != 0
            or screen.get('passed') is not False or before_context is None
            or not (screen.get('collision') is True or screen.get('ik_reachable') is False)):
        return
    if public_context(adapter) != before_context:
        return
    geometry=candidate_geometry(adapter,candidate)
    if detail.get('route_feedback_geometry',geometry)!=geometry:
        return
    memory = getattr(adapter, '_route_rejections', None)
    if memory is None or memory['context'] != before_context:
        memory = adapter._route_rejections = {'context': before_context, 'candidates': {}}
    memory['candidates'][identity(candidate)] = {
        'screen': {key: screen.get(key) for key in
            ('collision', 'ik_reachable', 'path_min_clearance_m')},
        'reason': receipt['stop_reason'], 'plan_sha256':geometry}


def apply(adapter, candidates):
    memory = getattr(adapter, '_route_rejections', None)
    if not memory or memory['context'] != public_context(adapter):
        adapter._route_rejections = None
        return candidates
    result = []
    for candidate in candidates:
        blocked = memory['candidates'].get(identity(candidate))
        if blocked is None or blocked['plan_sha256']!=candidate_geometry(adapter,candidate):
            result.append(candidate);continue
        current = copy.deepcopy(candidate)
        current['consequences'].update(blocked['screen'], screen_scope='hand_mesh_observed_space')
        current['consequences']['evidence_ids'].append('full-route-rejection:'+memory['context'])
        current['last_failure'] = blocked['reason']
        result.append(current)
    return result
