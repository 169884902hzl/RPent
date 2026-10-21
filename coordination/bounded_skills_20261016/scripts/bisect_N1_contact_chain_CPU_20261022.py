"""Isolate contact-chain changes on retained public measurements, without RPC."""
import argparse
import copy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace

from profile_user1050_saved_CPU_20261021 import RecordedFrames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--loops', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-grasp-search', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    import numpy as np
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_runtime import MeasuredScene

    saved = pickle.loads(args.checkpoint.read_bytes())
    runtime = saved['public_runtime']
    row = json.loads(args.loops.read_text().splitlines()[0])
    request = row['request']
    selected = next(c for c in request['candidates'] if c['id'] == row['decision']['candidate_ids'][0])
    key = selected['parameters']['anchor_id']
    # These are public observable fields, not body positions from the simulator.
    cache = saved['physics']['actuator_state']['observation_state']['cache']
    observed = {key: cache[key] for key in (
        'robot0_eef_pos', 'robot0_eef_quat', 'robot0_gripper_qpos', 'robot0_joint_pos')}
    frame_root, = (args.episode/'restored_captures').iterdir()
    capture_step = max(e['capture_step'] for anchor in request['anchors'] for e in anchor['evidence'])
    class RetainedFrames(RecordedFrames):
        def save(self, name, value, *, step=-1):
            path = self.artifact_path(name, step=step)
            with np.load(path) as data:
                np.testing.assert_array_equal(value, data[data.files[0]])
            return str(path)
    store = RetainedFrames(frame_root, capture_step)
    scene = object.__new__(MeasuredScene)
    vars(scene).update(copy.deepcopy(runtime['scene']))
    scene.toolkit = SimpleNamespace(_state=store)
    mask_matches = []
    # Retain identity from the checkpoint, but consume this arm's actual
    # masks and depth. A stored mask hash must exist in the new capture.
    for anchor in request['anchors']:
        entity = scene.entities[anchor['id']]
        centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
        entity = replace(entity, xyz=tuple(centre), lower=tuple(centre-size/2),
            upper=tuple(centre+size/2), source_step=capture_step)
        scene.entities[entity.id] = entity
        if entity.id != key:
            continue
        views = {}
        for camera, ref in scene.perception_evidence[entity.id].get('sam_mask_files', {}).items():
            mask_name = Path(ref['path']).parent.name
            if not store.artifact_path(mask_name).exists():
                # Match only among masks actually retained at this capture,
                # using the previous camera's public 3D instance identity.
                prior = runtime['scene']['measurement_views'][entity.id][camera]
                options = []
                world = store.load(camera+'_world_high.npz')
                for path in frame_root.glob(f'v6_sam_{camera}_*.npz/{capture_step:02d}.npz'):
                    with np.load(path) as data:
                        candidate_mask = data[data.files[0]].astype(bool)
                    points = world[candidate_mask]
                    if len(points):
                        distance = float(np.linalg.norm(np.median(points, axis=0)-prior.xyz))
                        options.append((distance, path.parent.name))
                options.sort()
                aliases = None
                if len(options)>1 and options[1][0]-options[0][0]<.01:
                    masks = [store.load(option[1]).astype(bool) for option in options[:2]]
                    aliases = float((masks[0]&masks[1]).sum()/(masks[0]|masks[1]).sum())
                if (not options or options[0][0] > .01
                        or (aliases is not None and aliases < .99)):
                    raise ValueError('current retained masks cannot identify the previous public instance: '+
                        str((entity.id, camera, options)))
                mask_name = options[0][1]
                mask_matches.append({'anchor': entity.id, 'camera': camera, 'selected': mask_name,
                    'nearest_distance_m': options[0][0], 'next_distance_m': options[1][0] if len(options)>1 else None,
                    'near_duplicate_mask_iou': aliases})
            mask = store.load(mask_name).astype(bool)
            expected_mask_hash = mask_name.rsplit('_', 1)[-1].removesuffix('.npz')
            if hashlib.sha256(mask.tobytes()).hexdigest()[:16] != expected_mask_hash:
                raise ValueError('recorded mask identity changed')
            views[camera] = store.load(camera+'_world_high.npz')[mask]
        if views:
            scene.cache_independent_views(entity, views)
            from robots.libero.v5_perception_geometry import fuse_cloud
            cameras = list(views)
            primary = 'agentview' if 'agentview' in views else cameras[0]
            secondary = [camera for camera in cameras if camera != primary]
            if secondary:
                points, _, _ = fuse_cloud(views[primary], [(views[secondary[0]], 1.)],
                    trim_depth_tails=scene.fusion_depth_trim_v2)
            else:
                points = views[primary]
            scene.measurement_clouds[entity.id] = points
    adapter = object.__new__(MeasuredSkillAdapter)
    vars(adapter).update(copy.deepcopy(runtime['adapter']))
    adapter.scene = scene
    adapter.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: observed))
    adapter.ex = SimpleNamespace(toolkit=scene.toolkit, instruction=request['instruction'])
    adapter.record_public_geometry = False
    adapter._base_geometry = adapter._base_geometry_cache = None
    adapter._capture_obstacles = adapter._self_filtered_capture = None
    adapter._screen_cache, adapter._instance_cache, adapter._grasp_geometry_cache = {}, {}, {}
    adapter.plans, adapter.committed_grasps = {}, {}
    adapter.public_geometry_evidence = {}
    adapter.candidate_diagnostics = []
    adapter.schema6_v1 = adapter.lazy_planning_v1 = adapter.rendered_self_filter_v1 = True
    adapter.precontact_instance_surface_v1 = True
    np.testing.assert_allclose(measured_robot(adapter.p)['eef_xyz_m'], request['robot']['eef_xyz_m'], atol=1e-12)
    entity = scene.entities[key]
    anchor = next(a for a in request['anchors'] if a['id'] == key)
    # A different perception capture must not be called an exact reproduction.
    np.testing.assert_allclose(entity.xyz, anchor['xyz_m'], atol=1e-12)
    plan = adapter.grasp_geometry(entity)
    adapter.plans[key] = plan
    actual_attempts = row['execution_details'][1]['execution']['internal_planning_attempts']
    variant = (dict(actual_attempts[0]['parameters']) if args.compare_grasp_search
        else {'anchor_id': key, 'approach': 'above', 'path': 'over'})
    adapter._commit_grasp({'skill': 'move_to', 'parameters': variant})
    entry = adapter._route('move_to', variant)[-1]
    plan = adapter.plans[key]
    ingress = plan.get('contact_route', [{'xyz_m': plan['xyz_m'], 'quat_xyzw': plan['quat_xyzw']}])
    if not args.compare_grasp_search:
        actual_lift = next(a['screen'] for a in actual_attempts
            if a['parameters'].get('approach') == 'above'
            and a['screen'].get('contact_sequence_stage') == 'attached_initial_lift')
        np.testing.assert_allclose(ingress[-1]['xyz_m'], actual_lift['ik_checks'][0]['xyz_m'], atol=1e-10)
    approach = adapter._candidate('move_to', variant, complete=True)
    screen = adapter._cloud_and_ik(key, contact=True)
    if screen.ik.last_solution is not None:
        screen = screen.continuing_route()
    before = screen([entry, *ingress])
    args.output.mkdir(parents=True, exist_ok=False)
    if args.compare_grasp_search:
        actual = actual_attempts[0]['screen']
        np.testing.assert_allclose(before['at']['xyz_m'], actual['at']['xyz_m'], atol=1e-10)
        assert before['target_counts'] == actual['target_counts']
        # Compare the existing eager proposal search on the same measured
        # surface. No sampler parameters, collision allowances or IK limits
        # change, and no simulation/RPC is used.
        adapter.lazy_planning_v1 = False
        adapter._screen_cache.clear()
        alternate = adapter._compute_grasp_geometry(entity)
        result = {'scope': 'same retained public inputs; lazy first proposal versus existing full grasp search',
            'source': str(args.source), 'checkpoint': str(args.checkpoint),
            'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            'rpc_calls': 0, 'physics_steps': 0, 'training': False,
            'reproduced_collision_pose_and_target_counts': True,
            'retained_mask_matches': mask_matches, 'lazy_plan': plan,
            'lazy_ingress': before, 'existing_eager_plan': alternate,
            'candidate_diagnostics': adapter.candidate_diagnostics}
        (args.output/'summary.json').write_text(json.dumps(result, indent=2,
            default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v))+'\n')
        print(json.dumps({'lazy_ingress': before['reason'], 'existing_eager_plan': alternate,
            'output': str(args.output)}, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v)))
        return
    captured = []
    original = PublicRouteScreen.__call__

    def capture(screen, *positional, **kwargs):
        raw = pickle.dumps((screen, positional, kwargs), protocol=5)
        result = original(screen, *positional, **kwargs)
        index = len(captured)
        path = args.output/f'route_{index:02d}.pkl.gz'
        path.write_bytes(gzip.compress(raw, compresslevel=1, mtime=0))
        captured.append({'input': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'payload_points': len(screen.payload), 'target_points': len(screen.target),
            'scene_points': len(screen.points), 'poses': positional[0], 'result': result})
        return result

    PublicRouteScreen.__call__ = capture
    after = adapter._screen_contact_sequence(key, entry, approach='above')
    result = {'scope': 'public saved initial measurements; isolates 03552 contact-chain extension',
        'training': False, 'rpc_calls': 0, 'physics_steps': 0,
        'source': str(args.source), 'anchor': key, 'plan': plan, 'approach': approach,
        'retained_mask_matches': mask_matches,
        'checkpoint': str(args.checkpoint),
        'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        'owning_failure_receipt': row['receipts'][0],
        'before_ingress_only': before, 'after_contact_chain': after, 'captured': captured}
    (args.output/'summary.json').write_text(json.dumps(result, indent=2,
        default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v))+'\n')
    print(json.dumps({'before': {k: before.get(k) for k in ('passed', 'reason')},
        'after': {k: after.get(k) for k in ('passed', 'reason', 'contact_sequence_stage')},
        'output': str(args.output)}))


if __name__ == '__main__':
    main()
