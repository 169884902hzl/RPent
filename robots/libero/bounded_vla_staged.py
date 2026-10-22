"""Measured preparation and placement for an explicitly selected VLA option."""
import math
from time import perf_counter

import numpy as np


def estimate_steps(adapter, parameters):
    """Estimate overhead from public bounds and the existing executor limits."""
    robot=adapter.robot();start=np.asarray(robot['eef_xyz_m'])
    source=adapter.scene.entities.get(parameters['anchor_id'])
    target=adapter.scene.entities.get(parameters.get('target_id'))
    if source is None:
        return 0
    transfer=parameters['mode'] in {'on','in'} and adapter.held==source.id and target is not None
    anchor=target if transfer else source
    centre=(np.asarray(anchor.lower)+anchor.upper)/2
    distance=float(np.linalg.norm(start-centre))+.16
    if transfer:
        distance+=max(.12,float(anchor.upper[2]-anchor.lower[2]))
    travel=math.ceil(distance/adapter.config.translation_speed_m_s*adapter.config.hz)
    return travel+adapter.config.endpoint_settle_steps*(3 if transfer else 1)+(15 if transfer else 0)


def component(adapter, skill, parameters):
    """Reuse the selected executor, retaining its full trace as internal evidence."""
    started=perf_counter();before=adapter.p.env.execution_budget()['used_sim_steps']
    candidate=adapter._candidate(skill,parameters,complete=True)
    if candidate is None:
        return {'skill':skill,'parameters':parameters,'success':False,'steps_used':0,
            'reason':'public_component_unavailable','wall_s':perf_counter()-started}
    receipt_start=len(adapter.receipts);detail_start=len(adapter.details)
    try:
        receipt=adapter._execute_one(adapter.latest_request,candidate)
    finally:
        # The model chose one compound call_vla. Its internal controls stay
        # in execution details; they are not additional model selections.
        del adapter.receipts[receipt_start:]
    return {'skill':skill,'parameters':parameters,'receipt':receipt,
        'success':receipt['outcome']=='success','reason':receipt['stop_reason'],
        'steps_used':adapter.p.env.execution_budget()['used_sim_steps']-before,
        'execution_detail_indices':list(range(detail_start,len(adapter.details))),
        'wall_s':perf_counter()-started}


def refresh_selected(adapter, parameters):
    source=adapter.scene.entities.get(parameters['anchor_id'])
    target=adapter.scene.entities.get(parameters.get('target_id'))
    adapter._incremental_touched.update(k for k in (parameters['anchor_id'],parameters.get('target_id')) if k)
    adapter.refresh(names=adapter._vla_measurement_names(source,target))


def prepare(adapter, parameters):
    """Stage at the measured source, or carry an existing grip above its target."""
    started=perf_counter();before=adapter.p.env.execution_budget()['used_sim_steps']
    transfer=parameters['mode'] in {'on','in'} and adapter.held==parameters['anchor_id']
    skill='carry_to' if transfer else 'move_to'
    arguments=({'target_id':parameters['target_id']} if transfer
        else {'anchor_id':parameters['anchor_id']})
    result=component(adapter,skill,arguments)
    if result['success'] and not (adapter.p.env.terminated or adapter.p.env.truncated):
        refresh_selected(adapter,parameters)
    return {'success':result['success'],'mode':'measured_anchor','component':result,
        'steps_used':adapter.p.env.execution_budget()['used_sim_steps']-before,
        'wall_s':perf_counter()-started,'pose_source':'existing_public_contact_plan_or_measured_bounds',
        'private_object_pose_used':False}


def transport(adapter, parameters):
    """A policy failure can still leave the measured grip needed for placement."""
    started=perf_counter();before=adapter.p.env.execution_budget()['used_sim_steps']
    robot=adapter.robot()
    held=(adapter.held==parameters['anchor_id']
        and adapter.holding_aperture(robot['gripper_opening_m'])[0])
    components=[]
    reason='public_grip_unverified'
    if held:
        for skill,arguments in (('carry_to',{'target_id':parameters['target_id']}),
                ('lower',{'target_id':parameters['target_id']}),('release',{})):
            if adapter.p.env.terminated or adapter.p.env.truncated:
                reason='native_stop';break
            result=component(adapter,skill,arguments);components.append(result)
            reason=result['reason']
            if not result['success']:
                break
    return {'components':components,'reason':reason,
        'steps_used':adapter.p.env.execution_budget()['used_sim_steps']-before,
        'wall_s':perf_counter()-started,'public_grip_verified_before_transport':held,
        'success_requires_final_public_or_native_completion':True,'private_object_pose_used':False}
