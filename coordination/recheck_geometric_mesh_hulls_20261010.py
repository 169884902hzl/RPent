"""Recheck stored poses with robot STL hulls, without running or scoring a policy."""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_array(path):
    with np.load(path) as archive:
        if len(archive.files) != 1:
            raise ValueError('one preserved public array required')
        return archive[archive.files[0]]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--new-module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    manifest = json.loads((args.report / 'manifest.json').read_text())
    plans = {}
    for reference in manifest['plans']:
        path = root / reference['path']
        plan = json.loads(path.read_text())
        plans[path.parent.parent.parent.name + '/' + path.parent.parent.name] = plan
    new = load_module(args.new_module, 'staged_robot_mesh_hulls')
    args.output.mkdir(parents=True, exist_ok=False)
    cache, modules, records = {}, {}, []
    for item in map(json.loads, (args.report / 'rows.jsonl').open()):
        if not any(word in item['group'] for word in ('bowl_coherent', 'box_coherent')):
            continue
        plan = plans[item['group']]
        source = Path(plan['source_path'])
        if source not in modules:
            path = source / 'robots/libero/v5_geometric_grasp.py'
            expected = next(r['sha256'] for r in plan['source_snapshot']['files']
                            if r['relative_path'] == 'robots/libero/v5_geometric_grasp.py')
            if pin(path)['sha256'] != expected:
                raise ValueError('registered geometry module changed')
            old = load_module(path, 'recorded_robot_bounds_' + str(len(modules)))
            xml = next(iter(plan['conditions'].values()))['overrides']['geometric_gripper_xml']
            modules[source] = old, old.panda_geometry(xml), new.panda_geometry(xml)
        old, old_geometry, new_geometry = modules[source]
        ledger = root / item['input']
        if ledger not in cache:
            if pin(ledger)['sha256'] != item['input_sha256']:
                raise ValueError('closed physical evidence changed')
            cache[ledger] = [json.loads(line) for line in ledger.open()]
        raw = cache[ledger][item['line']-1]
        first = raw.get('first_attempt') or {}
        ranks = (first.get('receipt') or {}).get('geometric_grasp_rankings') or []
        if not ranks:
            continue
        rank = ranks[-1]
        directory, step = Path(raw['output_dir']), rank['measurement_step']
        filename = f'{step:02d}.npz'
        state_path = directory / 'states.json'
        state = next(s['state'] for s in json.loads(state_path.read_text())['steps'] if s['step_idx'] == step)
        cloud_path = directory / ('analytic_target_' + rank['entity'] + '.npz') / filename
        target = old._voxel(load_array(cloud_path), .002)
        world_paths = [directory / (camera + '_world_high.npz') / filename for camera in ('agentview', 'wrist')]
        scene = np.concatenate([load_array(p).reshape(-1, 3) for p in world_paths])
        # Keep the old self-filter and opposition fits. Only mesh collision changes.
        opening = float(np.abs(state['robot0_gripper_qpos']).sum())
        scene, _ = old.remove_measured_hand(scene, state['robot0_eef_pos'], state['robot0_eef_quat'], old_geometry, opening)
        scene = old._voxel(scene)
        obstacles = scene[cKDTree(target).query(scene)[0] >= .006]
        tree = cKDTree(obstacles) if len(obstacles) else None
        candidates, recovered = copy.deepcopy(rank['candidates']), []
        for candidate in candidates:
            if candidate['rejected'] != ['observed_scene_or_target_intersects_actual_gripper_bounds']:
                continue
            rotation = Rotation.from_quat(candidate['body_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -math.pi/2).as_matrix()
            contact, stage = np.asarray(candidate['xyz']), np.asarray(candidate['approach_xyz'])
            collision = []
            for fraction in np.linspace(0, 1, 16):
                pose = stage + fraction * (contact - stage)
                hits = new.collision_counts(obstacles, pose, rotation, new_geometry, .08)
                target_hits = new.collision_counts(target, pose, rotation, new_geometry, .08)
                if any(hits.values()) or any(target_hits.values()):
                    collision.append({'fraction': float(fraction), 'scene': hits, 'target': target_hits})
                    break
            for fraction in np.linspace(0, 1, 11):
                pose = contact + [0., 0., .1 * fraction]
                hits = new.collision_counts(obstacles, pose, rotation, new_geometry, candidate['width_m'])
                if any(hits.values()):
                    collision.append({'lift_fraction': float(fraction), 'scene': hits})
                    break
            candidate['convex_mesh_collision_recheck'] = collision
            if not collision:
                candidate['rejected'] = []
                clearance = min(float(tree.query(contact)[0]), .2) if tree else .2
                angle = float((Rotation.from_quat(candidate['body_quat_xyzw'])
                               * Rotation.from_quat(state['robot0_eef_quat']).inv()).magnitude())
                candidate['score'] = candidate['antipodal_quality'] + clearance/.2 - .25 * angle/math.pi
                recovered.append(candidate['id'])
        candidates.sort(key=lambda r: (bool(r['rejected']), -r.get('score', -1), r['id']))
        before = next((c['id'] for c in rank['candidates'] if not c['rejected']), None)
        after = next((c['id'] for c in candidates if not c['rejected']), None)
        ranked_path = args.output / (item['case'] + '_candidates.json')
        ranked_path.write_text(json.dumps(candidates) + '\n')
        row = {'case': item['case'], 'group': item['group'], 'state_sha256': item['state_sha256'],
            'before_best': before, 'after_best': after, 'recovered_candidates': recovered,
            'newly_feasible': before is None and after is not None, 'best_changed': before != after,
            'candidate_records': pin(ranked_path), 'public_inputs': [pin(cloud_path), pin(state_path), *map(pin, world_paths)],
            'old_geometry': pin(source / 'robots/libero/v5_geometric_grasp.py'),
            'robot_meshes': new_geometry['references'], 'physical_validation': False}
        records.append(row)
        print(json.dumps({'case': row['case'], 'recovered': len(recovered), 'best_changed': row['best_changed']}), flush=True)
    path = args.output / 'rows.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in records))
    result = {'records': pin(path), 'producer': pin(Path(__file__)), 'new_module': pin(args.new_module),
        'input': pin(args.report / 'rows.jsonl'), 'n': len(records),
        'newly_feasible': sum(r['newly_feasible'] for r in records),
        'best_changed': sum(r['best_changed'] for r in records),
        'groups': {g: {'n': sum(r['group'] == g for r in records),
                       'newly_feasible': sum(r['group'] == g and r['newly_feasible'] for r in records),
                       'best_changed': sum(r['group'] == g and r['best_changed'] for r in records)}
                   for g in Counter(r['group'] for r in records)},
        'limits': ['Offline pose feasibility is not successful grasp evidence.',
                   'Only AABB-rejected measured candidate poses are rechecked; normal and width rejections stay rejected.'],
        'private_pose_or_contact_used': False, 'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
