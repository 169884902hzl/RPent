"""Private authoring transport from a CPU layout to a rendered original world."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from robots.libero.bounded_train_layouts import ORIGINAL_SUITES, SEED_RANGE


def authored_world_path(generated: dict, original_path: Path, episode: dict) -> Path:
    """Validate a private added-asset world against its original train task."""
    from robots.libero.bounded_layout_distractors import section

    layout = generated['layout']
    parent = layout['parent']
    if (parent.get('split') != 'train' or parent.get('suite') not in ORIGINAL_SUITES
            or any(parent.get(key) or layout.get(key) for key in ('PRO', 'D2', 'confirmation'))
            or any(parent[key] != episode[key] for key in ('suite', 'task', 'seed'))
            or not SEED_RANGE[0] <= layout['layout_seed'] <= SEED_RANGE[1]):
        raise ValueError('authored world requires the same original train parent')
    witness = layout['predicate_witness']
    if not all(witness.get(key) is True for key in ('native_predicates_satisfied',
            'nonintersecting', 'instruction_identity_consistent')):
        raise ValueError('authored world lacks its independent CPU witness')
    world = generated['authored_world']
    original = original_path.read_bytes()
    if hashlib.sha256(original).hexdigest() != world['original_bddl_sha256']:
        raise ValueError('authored world belongs to another original BDDL')
    path = Path(world['bddl']['path']).resolve(strict=True)
    raw = path.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != world['bddl']['sha256']
            or world['bddl']['sha256'] != world['authored_bddl_sha256']):
        raise ValueError('authored BDDL changed after CPU validation')
    old, new = original.decode(), raw.decode()
    for name in ('language', 'goal', 'domain', 'fixtures', 'obj_of_interest'):
        if old[slice(*section(old, name))] != new[slice(*section(new, name))]:
            raise ValueError('authored world changed original task section: '+name)
    return path


def materialize_original_layout(facade, primitives, generated, *, bddl_sha256):
    """Create a fresh sensor phase while preserving authored integration state.

    CPU construction deliberately has no camera observables. Its native and
    sensor buffers are not a rendered branchpoint. Every measured branch must
    instead capture the complete state after this one-time materialization.
    """
    layout = generated['layout']
    parent = layout['parent']
    if (parent.get('split') != 'train' or parent.get('suite') not in ORIGINAL_SUITES
            or any(layout.get(key) or parent.get(key) for key in ('PRO', 'D2', 'confirmation'))
            or not SEED_RANGE[0] <= layout['layout_seed'] <= SEED_RANGE[1]
            or layout.get('identity_domain') != 'own_original_train_layout'):
        raise ValueError('only registered own-layout original train construction is allowed')
    if not generated['actuator_state'].get('integration'):
        raise ValueError('constructed layout lacks complete integration state')
    physics = facade.snapshot()
    if physics['bddl_sha256'] != bddl_sha256:
        raise ValueError('constructed layout belongs to another original task')
    if any(physics['task'][key] != parent[key] for key in ('suite', 'task', 'seed')):
        raise ValueError('constructed layout parent and original runtime differ')
    physics['sim_state'] = copy.deepcopy(generated['sim_state'])
    physics['actuator_state'] = copy.deepcopy(generated['actuator_state'])
    # Camera configuration differs here. Restore physical integration and
    # controller/RNG, then let the rendered world sample its own sensors.
    for key in ('observation_state', 'native_data'):
        physics['actuator_state'].pop(key, None)
    physics['native_success_event_count'] = 0
    observed = facade.restore(physics)
    primitives.env.last_obs = observed
    primitives.env.terminated = primitives.env.truncated = False
    primitives.set_obs(observed)
    actual = facade.snapshot()
    expected = generated['actuator_state']['integration']['sha256']
    if actual['actuator_state']['integration']['sha256'] != expected:
        raise RuntimeError('authored integration state changed during materialization')
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    return {'model_visible': False, 'layout_seed': layout['layout_seed'],
        'integration_sha256': expected,
        'canonical_physics_sha256': snapshot_digest(actual),
        'constructor_full_state_identity_reused': False,
        'sensor_phase': 'fresh_target_environment_observables',
        'branch_rule': 'capture complete rendered physics, runtime, controller and RNG before any branch'}
