"""Public-anchor preparation for an explicitly selected contact option."""
from robots.libero.bounded_permissive import move
from robots.libero.bounded_vla_staged import component


def prepare_contact(adapter, parameters, *, push=False):
    key = parameters['anchor_id']
    start = adapter.p.env.execution_budget()['used_sim_steps']
    traces, stages = [], []
    if key not in adapter.plans:
        entity = adapter.scene.entities.get(key)
        points = adapter.scene.measurement_clouds.get(key)
        contact = adapter._surface_contact_plan(entity, points) if entity is not None and points is not None and len(points) >= 40 else None
        if contact is None:
            return {'success': False, 'steps_used': 0, 'stop_reason': 'public_contact_plan_missing', 'trace': []}
        adapter.plans[key] = contact
    # Endpoints come from the selected public instance's plan, never a goal.
    adapter._commit_grasp({'skill': 'move_to', 'parameters': {'anchor_id': key}})
    for skill in ('move_to', 'descend'):
        route = adapter._route(skill, {'anchor_id': key})
        if not route:
            return {'success': False, 'steps_used': adapter.p.env.execution_budget()['used_sim_steps']-start,
                'stop_reason': 'public_contact_route_missing', 'trace': traces, 'stages': stages}
        result = move(adapter.p, route[-1], gripper=adapter.gripper_command, config=adapter.config)
        traces.extend(result['trace']);stages.append({'skill': skill, 'endpoint': route[-1], **result})
        if adapter.p.env.terminated or adapter.p.env.truncated:
            break
    adapter.active = key
    if not push and not (adapter.p.env.terminated or adapter.p.env.truncated):
        close = component(adapter, 'set_gripper', {'mode': 'close'})
        stages.append(close)
    # Only the following guarded contact increments retain route screening.
    return {'success': not adapter.p.env.truncated,
        'steps_used': adapter.p.env.execution_budget()['used_sim_steps']-start,
        'stop_reason': 'native_stop' if adapter.p.env.terminated else 'public_preparation_complete',
        'trace': traces, 'stages': stages, 'anchor_id': key, 'private_geometry_used': False}
