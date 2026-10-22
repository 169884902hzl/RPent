"""Private original-train world authoring with existing LIBERO assets.

These functions construct a new world. A named-state transplant is not an
exact fork of the original model; capture a fresh complete state afterwards.
Nothing here supplies coordinates or task predicates to a public request.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from robots.libero.bounded_train_layouts import ORIGINAL_SUITES


_IDENTIFIER = re.compile(r'^[a-z][a-z0-9_]*$')


def section(text: str, name: str) -> tuple[int, int]:
    """Locate one balanced original BDDL section without rewriting its tokens."""
    matches = list(re.finditer(r'\(\s*:'+re.escape(name)+r'\b', text, re.I))
    if len(matches) != 1:
        raise ValueError('expected one BDDL section: '+name)
    start = matches[0].start()
    depth, quoted, comment, escaped = 0, False, False, False
    for index in range(start, len(text)):
        value = text[index]
        if comment:
            comment = value != '\n'
            continue
        if quoted:
            if value == '"' and not escaped:
                quoted = False
            escaped = value == '\\' and not escaped
            continue
        if value == ';':
            comment = True
        elif value == '"':
            quoted = True
        elif value == '(':
            depth += 1
        elif value == ')':
            depth -= 1
            if depth == 0:
                return start, index+1
    raise ValueError('unbalanced original BDDL section: '+name)


def add_distractors(text: str, *, parent: dict, distractors: list[dict],
                    support_symbol: str, ranges: list[float],
                    available_assets: set[str]) -> tuple[str, dict]:
    """Add free objects and initial regions, retaining the exact task sentence/goal."""
    if (parent.get('split') != 'train' or parent.get('suite') not in ORIGINAL_SUITES
            or any(parent.get(key) for key in ('PRO', 'D2', 'confirmation'))):
        raise ValueError('distractors require an original train parent')
    rect = np.asarray(ranges, float)
    if (rect.shape != (4,) or not np.isfinite(rect).all()
            or not (rect[2:] > rect[:2]).all()):
        raise ValueError('finite support-relative sampling rectangle required')
    if not _IDENTIFIER.fullmatch(support_symbol):
        raise ValueError('invalid original support symbol')
    identities = [row['id'] for row in distractors]
    if not identities or len(set(identities)) != len(identities):
        raise ValueError('distinct new distractor identities required')
    for row in distractors:
        if (not _IDENTIFIER.fullmatch(row['id']) or not _IDENTIFIER.fullmatch(row['asset'])
                or row['asset'] not in available_assets):
            raise ValueError('distractor must use an installed original LIBERO asset')
        if re.search(r'(?<![a-z0-9_])'+re.escape(row['id'])+r'(?![a-z0-9_])', text, re.I):
            raise ValueError('distractor identity already occurs in original task')
    task = {name: text[slice(*section(text, name))] for name in ('language', 'goal')}
    region_lines, object_lines, init_lines = [], [], []
    coordinates = ' '.join(format(float(v), '.17g') for v in rect)
    for row in distractors:
        region = row['id']+'_initial_region'
        if re.search(r'\b'+re.escape(region)+r'\b', text, re.I):
            raise ValueError('distractor initial region already exists')
        region_lines.append(f'\n      ({region} (:target {support_symbol}) (:ranges (({coordinates}))))\n')
        object_lines.append(f"\n    {row['id']} - {row['asset']}\n")
        init_lines.append(f"\n    (On {row['id']} {support_symbol}_{region})\n")
    result = text
    for name, additions in (('regions', region_lines), ('objects', object_lines), ('init', init_lines)):
        _, stop = section(result, name)
        result = result[:stop-1]+''.join(additions)+result[stop-1:]
    assert all(result[slice(*section(result, name))] == original for name, original in task.items())
    return result, {'version': 'original-asset-distractors/1', 'parent': dict(parent),
        'original_bddl_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'authored_bddl_sha256': hashlib.sha256(result.encode()).hexdigest(),
        'distractors': distractors, 'support_symbol': support_symbol,
        'initial_sampling_ranges': rect.tolist(), 'task_language_and_goal_bytes_unchanged': True,
        'source': 'installed_original_LIBERO_assets', 'training_admission': False,
        'requires': 'nonintersecting layout and independent native-predicate witness before physical use'}


def transplant_named_state(source_model, source_data, target_model, target_data) -> dict:
    """Author a larger model from original named joints/bodies/actuators.

    The target's additional joints keep their sampled state. Native solver
    buffers and complete-state hashes cannot be reused across these models.
    """
    import mujoco

    widths = {0: (7, 6), 1: (4, 3), 2: (1, 1), 3: (1, 1)}
    counts = {'joints': 0, 'bodies': 0, 'actuators': 0}
    # Resolve identities/types first so a changed robot cannot be half copied.
    mappings = {}
    for kind, count in ((mujoco.mjtObj.mjOBJ_JOINT, source_model.njnt),
            (mujoco.mjtObj.mjOBJ_BODY, source_model.nbody),
            (mujoco.mjtObj.mjOBJ_ACTUATOR, source_model.nu)):
        pairs = []
        for index in range(count):
            name = mujoco.mj_id2name(source_model, kind, index)
            if kind == mujoco.mjtObj.mjOBJ_BODY and index == 0:
                continue
            if not name:
                raise ValueError('original authoring state has an unnamed movable component')
            other = mujoco.mj_name2id(target_model, kind, name)
            if other < 0:
                raise ValueError('authored model lost original identity: '+name)
            if kind == mujoco.mjtObj.mjOBJ_JOINT and source_model.jnt_type[index] != target_model.jnt_type[other]:
                raise ValueError('authored model changed original joint type: '+name)
            pairs.append((index, other))
        mappings[kind] = pairs
    for first, second in mappings[mujoco.mjtObj.mjOBJ_BODY]:
        target_model.body_pos[second] = source_model.body_pos[first]
        target_model.body_quat[second] = source_model.body_quat[first]
        counts['bodies'] += 1
    for first, second in mappings[mujoco.mjtObj.mjOBJ_JOINT]:
        nq, nv = widths[int(source_model.jnt_type[first])]
        a, b = source_model.jnt_qposadr[first], target_model.jnt_qposadr[second]
        target_data.qpos[b:b+nq] = source_data.qpos[a:a+nq]
        a, b = source_model.jnt_dofadr[first], target_model.jnt_dofadr[second]
        target_data.qvel[b:b+nv] = source_data.qvel[a:a+nv]
        counts['joints'] += 1
    for first, second in mappings[mujoco.mjtObj.mjOBJ_ACTUATOR]:
        target_data.ctrl[second] = source_data.ctrl[first]
        counts['actuators'] += 1
    target_data.time = source_data.time
    mujoco.mj_forward(target_model, target_data)
    return {**counts, 'exact_original_fork': False,
        'new_complete_state_required': True, 'private_authoring_only': True}


def transplant_original_world(source, target) -> dict:
    """Copy original joint state and command targets into an authored CPU world."""
    import copy

    from robots.libero.v5_branch_state import CONTROLLER_FIELDS

    audit = transplant_named_state(source.sim.model._model, source.sim.data._data,
        target.sim.model._model, target.sim.data._data)
    if len(source.env.robots) != len(target.env.robots):
        raise ValueError('authored world changed the robot count')
    for old, new in zip(source.env.robots, target.env.robots):
        old_grippers = old.gripper if isinstance(old.gripper, dict) else {'gripper': old.gripper}
        new_grippers = new.gripper if isinstance(new.gripper, dict) else {'gripper': new.gripper}
        for name, gripper in old_grippers.items():
            if type(gripper) is not type(new_grippers[name]):
                raise ValueError('authored world changed the gripper')
            new_grippers[name].current_action = copy.deepcopy(gripper.current_action)
        for name, controller in old.part_controllers.items():
            current = new.part_controllers[name]
            current.update(force=True)
            # A larger model has differently shaped dynamics caches. Only
            # command targets transfer; the target computes its own caches.
            for field in CONTROLLER_FIELDS:
                if hasattr(controller, field):
                    setattr(current, field, copy.deepcopy(getattr(controller, field)))
    return {**audit, 'controller_transfer': 'command_targets_only',
        'RNG': 'fresh_authored_world_seed; captured before branching'}
