"""Batch independent endpoint checks, retaining the source solver on failure.

Each request is (source_screen, xyz, quat). Consecutive poses of a route must
continue through the source warm solver; they are not independent endpoints.
"""
from collections import defaultdict
import hashlib
import time

import numpy as np

from .ik import BatchedDampedIK


def check_independent_ik(requests, *, iterations=128):
    started = time.perf_counter()
    results = [None] * len(requests)
    groups = defaultdict(list)
    stats = {'cache_hits': 0, 'dls_success': 0, 'source_fallback': 0,
             'batch_s': 0., 'fallback_s': 0., 'batches': [],
             'per_call': [None] * len(requests)}
    dependent_sources = set()
    for index, (source, xyz, quat) in enumerate(requests):
        continuity = source.route_joint_step_rad is not None
        if source.warm_start or continuity:
            if id(source) in dependent_sources:
                raise ValueError('dependent route poses must use the source warm solver')
            dependent_sources.add(id(source))
        reference = np.asarray(source.last_solution if source.last_solution is not None
                               else source.joints).copy()
        cache_key = (*map(float, xyz), *map(float, quat))
        if continuity:
            cache_key = (*cache_key, *reference)
        if cache_key in source.cache:
            t = time.perf_counter()
            results[index] = source.check(xyz, quat)
            stats['per_call'][index] = {'method': 'source_cache',
                                       'cache_wall_s': time.perf_counter()-t,
                                       'batch_amortized_s': 0., 'fallback_wall_s': 0.}
            stats['cache_hits'] += 1
            continue
        # Include the full public chain, not just the calibration/XML name.
        identity = [source.world_rotation.ravel(), source.world_offset,
                    source.site_offset, source.limits.ravel(),
                    [source.route_joint_step_rad or 0.]]
        for transform, axis in source.nodes:
            identity.extend([np.asarray(transform).ravel(),
                             np.r_[0.] if axis is None else np.r_[1., axis]])
        key = hashlib.sha256(np.concatenate(identity).tobytes()).hexdigest()
        groups[key].append((index, source, xyz, quat, reference, cache_key))
    for key, values in groups.items():
        source = values[0][1]
        kernel = BatchedDampedIK.from_source(source, iterations=iterations)
        continuity = source.route_joint_step_rad is not None
        if continuity:
            kernel.max_joint_step_rad = source.route_joint_step_rad
        references = np.array([v[4] for v in values])
        seeds = [np.array([v[1].joints for v in values])]
        if kernel.n == 7:
            seeds.extend([np.array([0., -.4, 0., -2.2, 0., 2., .75]),
                          np.array([.8, -.4, -.8, -2.2, .8, 2., -.75])])
        t = time.perf_counter()
        batch = kernel.solve_batch([v[2] for v in values], [v[3] for v in values],
                                   references, seeds=seeds, continuity=continuity)
        elapsed = time.perf_counter() - t
        stats['batch_s'] += elapsed
        stats['batches'].append({'batch_id': key, 'n': len(values), 'wall_s': elapsed,
                                'amortized_per_call_s': elapsed / len(values)})
        for local_index, (index, source, xyz, quat, reference, cache_key) in enumerate(values):
            cost = {'batch_id': key, 'cache_wall_s': 0.,
                    'batch_amortized_s': elapsed / len(values), 'fallback_wall_s': 0.}
            if not batch['solution_found'][local_index]:
                # A numerical miss is not an infeasibility certificate. The
                # original incoming source state/seed is still untouched.
                t = time.perf_counter()
                results[index] = source.check(xyz, quat)
                cost['fallback_wall_s'] = time.perf_counter() - t
                stats['fallback_s'] += cost['fallback_wall_s']
                cost['method'] = 'source_fallback'
                stats['per_call'][index] = cost
                stats['source_fallback'] += 1
                continue
            q = batch['joint_positions_rad'][local_index]
            result = {
                'version': 'public-panda-batched-dls/2', 'solution_found': True,
                'source': 'static_robot_description_and_public_proprioception',
                'robot_xml': source.reference,
                'solves': [{
                    'solution_found': True,
                    'position_error_m': float(batch['position_error_m'][local_index]),
                    'orientation_error_rad': float(batch['orientation_error_rad'][local_index]),
                    'joint_positions_rad': q.tolist(),
                    'function_evaluations': int(batch['function_evaluations'][local_index]),
                    'joint_margin_min_rad': float(np.minimum(q-source.limits[:, 0],
                                                            source.limits[:, 1]-q).min()),
                    'method': 'independent_endpoints_batched_damped_least_squares'}],
                'arm_collisions_checked': False, 'servo_convergence_certified': False,
                'numerical_failure_is_not_proof_of_infeasibility': True}
            if continuity:
                result['local_continuation'] = {
                    'max_joint_step_rad': source.route_joint_step_rad,
                    'from_joint_positions_rad': reference.tolist(),
                    'numerical_search_bound_only': True}
            if source.warm_start or continuity:
                source.last_solution = q.copy()
            source.cache[cache_key] = result
            results[index] = result
            cost['method'] = 'batch_dls'
            stats['per_call'][index] = cost
            stats['dls_success'] += 1
    stats['total_s'] = time.perf_counter() - started
    return results, stats
