"""Inspect captured public payload screens; no simulation, model or SAM calls."""

import argparse
import copy
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-pre-contact-scene', action='store_true')
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import numpy as np
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation

    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.bounded_self_filter import gripper_at_measured_fingers

    directory = args.directory.resolve(strict=True)
    request = json.loads((directory/'first_self_request.json').read_bytes())
    summary = json.loads((directory/'replay/summary.json').read_bytes())
    raw = Path(summary['endpoint']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == summary['endpoint']['sha256']
    # Read only captured public caches and the static robot geometry.
    public = pickle.loads(raw)['public_runtime']
    reference = public['adapter']['payload_reference']
    robot = request['robot']
    samples = public['primitive']['_bounded_motion_samples']
    measured = samples[-1][1]
    np.testing.assert_array_equal(robot['eef_xyz_m'], measured['eef_xyz_m'])
    geometry = gripper_at_measured_fingers(public['adapter']['geometry'], measured['finger_positions_m'])
    step = max(e['capture_step'] for a in request['anchors'] for e in a['evidence'])
    captured = []
    for candidate in request['candidates']:
        if candidate['skill'] != 'carry_to':
            continue
        key = candidate['parameters']['target_id']
        files = [directory/f'bounded_screen_{key}_0_{name}.npz'/f'{step:02d}.npz'
            for name in ('scene', 'target', 'payload_local')]
        if not all(path.exists() for path in files):
            continue
        arrays = []
        for path in files:
            with np.load(path) as data:
                arrays.append(data[data.files[0]])
        scene, target, payload = arrays
        pose = {'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']}
        screen = PublicRouteScreen(scene, geometry, None, opening=robot['gripper_opening_m'],
            contact_points=target, payload_local=payload, initial_pose=pose)
        checks = []
        for shift in ([0., 0., 0.], [0., 0., .001], [0., 0., .01], [0., 0., .1]):
            value = {'xyz_m': (np.asarray(pose['xyz_m'])+shift).tolist(),
                'quat_xyzw': pose['quat_xyzw']}
            result = screen._geometry_at(value)
            checks.append({'shift_m': shift, 'geometry': result})
        initial_world = payload@Rotation.from_quat(pose['quat_xyzw']).as_matrix().T+pose['xyz_m']
        distances, indices = cKDTree(scene).query(initial_world)
        at = int(np.argmin(distances))
        obstacle = scene[indices[at]]
        pixels = []
        for camera in ('agentview', 'wrist'):
            path = directory/(camera+'_world_high.npz')/f'{step:02d}.npz'
            with np.load(path) as data:
                world = data[data.files[0]]
            values, ids = cKDTree(world.reshape(-1, 3)).query(obstacle)
            pixels.append({'camera': camera, 'nearest_pixel_yx': list(map(int,
                np.unravel_index(ids, world.shape[:2]))), 'distance_m': float(values)})
        captured.append({'candidate_id': candidate['id'], 'target_id': key,
            'files': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
            'points': list(map(len, arrays)), 'checks': checks,
            'initial_payload_scene_min_distance_m': float(distances[at]),
            'payload_point_m': initial_world[at].tolist(), 'obstacle_point_m': obstacle.tolist(),
            'reference_capture_step': reference['capture_step'],
            'obstacle_distance_to_reference_scene_m': float(cKDTree(reference['scene']).query(obstacle)[0]),
            'obstacle_distance_to_reference_target_m': float(cKDTree(reference['target']).query(obstacle)[0]),
            'obstacle_pixels': pixels})
    report = {'directory': str(directory), 'source': str(args.source.resolve()),
        'capture_step': step, 'rows': captured, 'physics_steps': 0, 'gpu_used': False,
        'private_scene_geometry_used': False, 'training': False,
        'scope': 'captured geometry probes only; not an IK certificate or executed path'}
    if args.compare_pre_contact_scene:
        from PIL import Image

        from robots.libero.bounded_offline_labels import FrozenSensors
        from robots.libero.bounded_skills import MeasuredSkillAdapter

        def load(name):
            path = directory/name/(f'{step:02d}'+Path(name).suffix)
            if path.suffix == '.json':
                return json.loads(path.read_bytes())
            if path.suffix == '.png':
                return np.asarray(Image.open(path))
            with np.load(path) as data:
                return data[data.files[0]]

        first_scene = min((directory/'bounded_screen_None_0_scene.npz').glob('*.npz'),
            key=lambda path: int(path.stem))
        with np.load(first_scene) as data:
            pre_contact_scene = data[data.files[0]]
        comparison = []
        for name in ('raised_scene', 'pre_contact_scene'):
            saved = copy.deepcopy(public)
            adapter = object.__new__(MeasuredSkillAdapter)
            vars(adapter).update(saved['adapter'])
            adapter.scene = SimpleNamespace(**saved['scene'])
            adapter.p = SimpleNamespace(env=FrozenSensors(measured, {}), **saved['primitive'])
            adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(
                latest_step=step, load=load)))
            adapter.record_public_geometry = False
            adapter._instance_cache.pop(robot['held_anchor_id'], None)
            adapter._screen_cache.clear()
            if name == 'pre_contact_scene':
                adapter.payload_reference['scene'] = pre_contact_scene
            screen = adapter._cloud_and_ik(captured[0]['target_id'])
            checks = []
            for shift in (0., .001, .01, .1):
                checks.append({'z_shift_m': shift, 'geometry': screen._geometry_at({
                    'xyz_m': (np.asarray(robot['eef_xyz_m'])+[0., 0., shift]).tolist(),
                    'quat_xyzw': robot['eef_quat_xyzw']})})
            comparison.append({'variant': name, 'checks': checks, 'payload_points': len(screen.payload),
                'stationary_veto': [row for row in adapter.instance_boundary_evidence[robot['held_anchor_id']]
                    if row.get('source') == 'pre_lift_stationary_scene_veto_current_mask']})
        report['static_scene_comparison'] = {'variants': comparison,
            'earliest_scene': str(first_scene), 'sam_calls': 0,
            'scope': 'same saved masks, no guided SAM rerun in either arm; earliest scene is conservative and still includes the old source surface; not a physical replay'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'rows': len(captured), 'capture_step': step}))


if __name__ == '__main__':
    main()
