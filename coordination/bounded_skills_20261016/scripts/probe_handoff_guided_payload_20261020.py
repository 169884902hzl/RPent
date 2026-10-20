"""Replay captured public handoff geometry with an owned live SAM service.

No simulator steps or private scene geometry are used. The client is CPU-only;
segmentation runs on the existing, explicitly supplied GPU service.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-report', type=Path, required=True)
    parser.add_argument('--implementation', type=Path, required=True)
    parser.add_argument('--payload-implementation', type=Path)
    parser.add_argument('--sam-assignment', type=Path, required=True)
    parser.add_argument('--target-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.public_report.read_bytes())
    source, directory = Path(report['source']), Path(report['directory'])
    sys.path.insert(0, str(source))
    import numpy as np
    from PIL import Image
    from scipy.spatial import cKDTree

    from robots.libero.bounded_offline_labels import FrozenSensors
    from robots.libero.bounded_motion import SmoothMotion
    from robots.libero import bounded_payload
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    spec = importlib.util.spec_from_file_location('proposed_public_skill_adapter', args.implementation)
    proposed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proposed)
    new_method = proposed.MeasuredSkillAdapter._guided_payload_pixels
    original = MeasuredSkillAdapter._guided_payload_pixels
    original_boundary = bounded_payload.complete_moving_boundary
    new_boundary = original_boundary
    if args.payload_implementation is not None:
        payload_spec = importlib.util.spec_from_file_location('proposed_payload', args.payload_implementation)
        payload = importlib.util.module_from_spec(payload_spec)
        payload_spec.loader.exec_module(payload)
        new_boundary = payload.complete_moving_boundary
    assignment = json.loads(args.sam_assignment.read_bytes())
    endpoint = json.loads((directory/'replay/summary.json').read_bytes())['endpoint']
    raw = Path(endpoint['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == endpoint['sha256']
    public = pickle.loads(raw)['public_runtime']
    request = json.loads((directory/'first_self_request.json').read_bytes())
    step = max(e['capture_step'] for a in request['anchors'] for e in a['evidence'])
    measured = public['primitive']['_bounded_motion_samples'][-1][1]
    np.testing.assert_array_equal(measured['eef_xyz_m'], request['robot']['eef_xyz_m'])

    def path(name):
        return directory/name/(f'{step:02d}'+Path(name).suffix)

    def load(name):
        p = path(name)
        if p.suffix == '.json':
            return json.loads(p.read_bytes())
        if p.suffix == '.png':
            return np.asarray(Image.open(p))
        with np.load(p) as data:
            return data[data.files[0]]

    key = args.target_id
    blockers = np.asarray([r['point_m'] for r in report['rows']])
    variants = []
    try:
        variant = 'current_measured_extent' if args.payload_implementation else 'current_depth_point_seed'
        for name, method in [('baseline', original), (variant, new_method)]:
            MeasuredSkillAdapter._guided_payload_pixels = method
            bounded_payload.complete_moving_boundary = (original_boundary if name == 'baseline' else new_boundary)
            saved = copy.deepcopy(public)
            adapter = object.__new__(MeasuredSkillAdapter)
            vars(adapter).update(saved['adapter'])
            adapter.scene = SimpleNamespace(**saved['scene'])
            adapter.scene.rpc = HttpRpcClient(assignment['sam3_url'])
            adapter.p = SimpleNamespace(env=FrozenSensors(measured, {}), **saved['primitive'])
            adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(
                latest_step=step, load=load, load_bytes=lambda name: path(name).read_bytes())))
            adapter.record_public_geometry = False
            held = request['robot']['held_anchor_id']
            adapter._instance_cache.pop(held, None)
            adapter._screen_cache.clear()
            started = time.perf_counter()
            calls = adapter.scene.calls
            screen = adapter._cloud_and_ik(key)
            checks = []
            for shift in (0., .001, .01, .1):
                pose = {'xyz_m': (np.asarray(measured['eef_xyz_m'])+[0., 0., shift]).tolist(),
                    'quat_xyzw': measured['eef_quat_xyzw']}
                checks.append({'z_shift_m': shift, 'geometry': screen._geometry_at(pose)})
            route = adapter._route('carry_to', {'target_id': key})
            planned = SmoothMotion(adapter.p, screen, adapter.config).prepare(route)
            variants.append({'variant': name, 'wall_s': time.perf_counter()-started,
                'sam_calls': adapter.scene.calls-calls, 'payload_points': len(screen.payload),
                'blocker_distances_to_remaining_scene_m': cKDTree(screen.points).query(blockers)[0].tolist(),
                'checks': checks, 'carry_route': route, 'carry_screen': planned[3],
                'boundary_evidence': adapter.instance_boundary_evidence.get(held)})
    finally:
        MeasuredSkillAdapter._guided_payload_pixels = original
        bounded_payload.complete_moving_boundary = original_boundary
    result = {'source': str(source), 'implementation': {'path': str(args.implementation),
        'sha256': hashlib.sha256(args.implementation.read_bytes()).hexdigest()},
        'payload_implementation': ({'path': str(args.payload_implementation),
            'sha256': hashlib.sha256(args.payload_implementation.read_bytes()).hexdigest()}
            if args.payload_implementation else None),
        'sam_assignment': str(args.sam_assignment), 'capture_step': step, 'variants': variants,
        'physics_steps': 0, 'private_scene_geometry_used': False, 'training': False,
        'gpu_allocation_added': False, 'live_gpu_sam_used': True,
        'scope': 'captured RGB-D geometry and live point SAM; not an executed handoff or a route IK certificate'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'variants': [{
        k: row[k] for k in ('variant', 'wall_s', 'sam_calls', 'payload_points')} for row in variants]}))


if __name__ == '__main__':
    main()
