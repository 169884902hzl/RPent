"""Own-layout perturbations of original train tasks; never reads PRO/MAX.

This generator owns private scene construction only. Its coordinates and task
witness are not exposed to the public perception/runtime input. The caller
must verify original train admission and evaluate a native predicate witness
in a separate CPU simulator before admitting a generated state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

VERSION = 'original-train-layout/6'
ORIGINAL_SUITES = {'libero_spatial','libero_object','libero_goal','libero_10','libero_90'}
SEED_RANGE = (11020000,11029999)


@dataclass(frozen=True)
class LayoutLimits:
    translation_m: float = .12
    yaw_rad: float = math.pi
    separation_m: float = .01
    confirmation_distance_m: float = .05
    attempts: int = 200
    placement_attempts: int = 100


def corners(item):
    """Conservative projected box at a proposed yaw, including its full size."""
    half=np.asarray(item['size_m'],float)[:2]/2
    xy=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*half
    c,s=math.cos(item['yaw_rad']),math.sin(item['yaw_rad'])
    return xy@np.array([[c,s],[-s,c]])+np.asarray(item['xyz_m'])[:2]


def overlap(a,b,margin):
    """Separating-axis test for tabletop oriented bounds, retaining a gap."""
    az,bz=a['xyz_m'][2],b['xyz_m'][2]
    if abs(az-bz)>=(a['size_m'][2]+b['size_m'][2])/2+margin:
        return False
    ac,bc=corners(a),corners(b)
    for poly in (ac,bc):
        for edge in (poly[1]-poly[0],poly[2]-poly[1]):
            axis=np.array([-edge[1],edge[0]])/np.linalg.norm(edge)
            aa,bb=ac@axis,bc@axis
            if aa.max()+margin<=bb.min() or bb.max()+margin<=aa.min():
                return False
    return True


def instruction_identity_check(objects, goals, instruction, axes):
    """Private authoring check for movable-source language grounding.

    The existing rule binder must select the original source identity after
    perturbation. Synthetic geometry here is private construction metadata,
    never a perception result or a model-visible state. Fixed fixture source
    poses are unchanged by this generator; their rules are not recreated.
    """
    from robots.libero.v5_oracle_policy import OriginalOraclePolicy, _kind, goal_clause
    from robots.libero.v5_state import Entity

    entities=[];identities={};movable={x['id'] for x in objects if x['movable']}
    for i,item in enumerate(objects):
        xy=corners(item);half_z=item['size_m'][2]/2;xyz=item['xyz_m']
        eid=f'construction-{i}'
        entities.append(Entity(eid,_kind(item.get('asset_type', item['id'])),tuple(xyz),
            (*xy.min(0),xyz[2]-half_z),(*xy.max(0),xyz[2]+half_z),True,0))
        identities[eid]=item['id']
    results=[]
    for goal in goals:
        source=goal[1]
        if source not in movable:
            continue
        binder=OriginalOraclePolicy(None)
        selected=binder.bind(source,entities,goal_clause(instruction,source),axes)
        actual=identities[selected.id] if selected is not None else None
        results.append({'source':source,'resolved':actual,'consistent':actual==source})
    return {'instruction_identity_consistent':all(r['consistent'] for r in results),
        'movable_sources':results,'source':'private_construction_geometry_and_existing_instruction_binding_rules',
        'scope':'source-identity rule check; not RGB-D binding accuracy or complete natural-language verification'}


def generate_layout(*, parent, objects, support, seed, witness_check,
                    confirmation_layouts=(), limits=LayoutLimits()):
    """Sample own offsets/yaws, reject intersections and failed task witnesses.

    ``witness_check`` receives proposed poses and must test native predicates
    in an independent CPU instance. Merely leaving goal text unchanged cannot
    establish that the perturbed task remains satisfiable.
    """
    if parent.get('split')!='train' or parent.get('suite') not in ORIGINAL_SUITES:
        raise ValueError('only frozen original train tasks are admitted')
    if parent.get('PRO') or parent.get('D2') or parent.get('confirmation'):
        raise ValueError('evaluation/confirmation states cannot enter perturbation labels')
    if not SEED_RANGE[0]<=seed<=SEED_RANGE[1]:
        raise ValueError('seed outside registered own-layout range')
    if not callable(witness_check):
        raise TypeError('independent native task witness callback required')
    rng=np.random.default_rng(seed)
    low,high=np.asarray(support['lower_m']),np.asarray(support['upper_m'])
    if not np.all(high>low) or len({x['id'] for x in objects})!=len(objects):
        raise ValueError('invalid support bounds or duplicate object identity')
    for item in objects:
        centre=np.asarray(item.get('local_centre_m',[0.,0.,0.]))
        values=np.r_[item['xyz_m'],item['size_m'],item['yaw_rad'],centre]
        if centre.shape!=(3,) or not np.isfinite(values).all() or not np.all(np.asarray(item['size_m'])>0):
            raise ValueError('finite positive measured/static object geometry required')
    fixed=[dict(x) for x in objects if not x['movable']]
    moving=[x for x in objects if x['movable']]
    excluded = {item['id']: np.asarray([old[symbol][:2]
        for old in confirmation_layouts
        for symbol in item.get('confirmation_match_symbols', [item['id']]) if symbol in old], float).reshape(-1, 2)
        for item in moving}

    def rejected(item, placed):
        footprint = corners(item)
        if not ((footprint >= low[:2]+limits.separation_m).all()
                and (footprint <= high[:2]-limits.separation_m).all()):
            return 'outside_free_support'
        c,s = math.cos(item['yaw_rad']),math.sin(item['yaw_rad'])
        position = np.asarray(item['xyz_m'])[:2]-np.array([[c,-s],[s,c]]) @ np.asarray(
            item.get('local_centre_m', [0., 0., 0.]))[:2]
        if len(excluded[item['id']]) and (np.linalg.norm(
                excluded[item['id']]-position, axis=1) < limits.confirmation_distance_m).any():
            return 'near_permanent_confirmation_layout'
        if any(overlap(item, other, limits.separation_m) for other in placed):
            return 'intersecting_object_bounds'
        return None

    reasons={}
    for attempt in range(limits.attempts):
        proposed=[dict(x) for x in fixed]
        bases=[np.asarray(x['xyz_m']) for x in moving]
        # Permute existing positions as well as offset/yaw them. This is our
        # generic sampler, independent of PRO swap/task names or definitions.
        order=rng.permutation(len(moving))
        strategy = 'offset_and_permute' if attempt % 2 == 0 else 'uniform_free_support'
        for i,item in enumerate(moving):
            # Re-sample this object's rejected placement without discarding
            # all already valid objects. Whole-layout rejection makes the
            # five-centimetre exclusion probability multiply across assets.
            for _ in range(limits.placement_attempts):
                pos = bases[order[i]].copy()
                if strategy == 'offset_and_permute':
                    pos[:2] += rng.uniform(-limits.translation_m, limits.translation_m, 2)
                else:
                    pos[:2] = rng.uniform(low[:2], high[:2])
                pos[2] = high[2]+item['size_m'][2]/2
                candidate = {**item, 'xyz_m': pos.tolist(),
                    'yaw_rad': float(item['yaw_rad']+rng.uniform(-limits.yaw_rad, limits.yaw_rad))}
                reason = rejected(candidate, proposed)
                if reason is None:
                    proposed.append(candidate)
                    break
                reasons[reason] = reasons.get(reason, 0)+1
            else:
                break
        if len(proposed) != len(objects):
            reasons['object_placement_exhausted'] = reasons.get('object_placement_exhausted', 0)+1
            continue
        reason = None
        if reason is None:
            witness=witness_check(proposed)
            if not isinstance(witness,dict) or witness.get('native_predicates_satisfied') is not True:
                reason='original_task_witness_failed'
            elif witness.get('nonintersecting') is False:
                reason='original_layout_witness_collision'
            elif witness.get('instruction_identity_consistent') is False:
                reason='original_instruction_binding_changed'
        if reason is not None:
            reasons[reason]=reasons.get(reason,0)+1
            continue
        return {'version':VERSION,'layout_seed':seed,'parent':parent,'objects':proposed,
            'limits':vars(limits),'attempt':attempt,'proposal_strategy':strategy,'rejected_attempts':reasons,
            'predicate_witness':witness,'PRO':False,'D2':False,'confirmation':False,
            'identity_domain':'own_original_train_layout',
            'confirmation_distance_metric':'world_xy_euclidean',
            'confirmation_distance_anchor':'object_body_origin',
            'source_policy':'own original train sampler; no PRO/MAX files or definitions'}
    raise ValueError('no admissible layout: '+str(reasons))
