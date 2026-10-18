# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Independently identify precontact-registration additions at an unchanged saved state."""
# ruff: noqa: E402 -- CPU GL selected before simulator imports
import argparse
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1',
    MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
    __EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/50_mesa.json',
    EGL_PLATFORM='surfaceless', LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
parser = argparse.ArgumentParser()
parser.add_argument('--jobs', default='9026_17')
parser.add_argument('--delta-tag', default='precontact_membership_CPU_20261018')
parser.add_argument('--include-blockers', action='store_true')
parser.add_argument('--output', type=Path, default=base/'reports/9026_17_precontact_added_pixels_CPU_20261018.json')
args = parser.parse_args()
sys.path.insert(0, str(root/'source_bounded_chunk_v3_offline_labels_20261018_c916ab1'))
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from OpenGL import GL
from robosuite.utils.binding_utils import MjRenderContextOffscreen
from scipy.spatial import cKDTree

from robots.libero.bounded_rgbd import render_measurement
from robots.libero.tools import _metric_depth, _world_from_depth
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

diagnosis = json.loads((base/'reports/9026_contact_blocker_pixels_CPU_20261018.json').read_text())
cases = {case['job']: case for case in diagnosis['cases']}
for job in args.jobs.split(','):
    if job not in cases:
        directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle_k4')
        row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[1])
        lift = next(candidate for candidate in row['candidate_screen_diagnostics'] if candidate.get('skill') == 'lift')
        key = 'bounded_screen_'+lift['parameters']['anchor_id']+'_1_scene'
        cases[job] = {'job': job, 'row': 1, 'capture_step': row['public_geometry_evidence'][key]['capture_step']}
results = []
for case in cases.values():
    if case['job'] not in args.jobs.split(','):
        continue
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+case['job'])).glob('*oracle_k4')
    rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
    row = rows[case['row']]
    reference = row['private_pre_execution_snapshot']
    raw = Path(reference['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == reference['sha256']
    saved = pickle.loads(raw)
    ledger = json.loads((directory.parent/'episodes.jsonl').read_bytes().splitlines()[0])
    env = ControlEnv(bddl_file_name=ledger['case']['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    context = mujoco.GLContext(1024, 1024)
    context.make_current()
    renderer = GL.glGetString(GL.GL_RENDERER).decode()
    assert 'llvmpipe' in renderer.lower()
    try:
        env.set_init_state(saved['sim_state'])
        restore_actuators(env, saved['actuator_state'])
        sim = env.env.sim
        error = float(np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])))
        assert error < 1e-8
        software = SimpleNamespace(make_current=context.make_current, free=lambda: None)
        with patch('robosuite.renderers.context.egl_context.EGLGLContext', return_value=software):
            normal = MjRenderContextOffscreen(sim, device_id=-1)
        normal.vopt.geomgroup[0], normal.vopt.geomgroup[1] = 0, 1
        views = []
        covered_additions = set()
        for view in [{'camera': camera, 'pixel': [0, 0]} for camera in ('agentview', 'wrist')]:
            camera = view['camera']
            u, v = view['pixel']
            capture = f"{case['capture_step']:02d}"
            metadata = json.loads((directory/(camera+'_metadata.json')/(capture+'.json')).read_text())
            high = {**metadata, 'intrinsic_K': (np.asarray(metadata['intrinsic_K'])
                *np.array([[4, 4, 4], [4, 4, 4], [1, 1, 1]])).tolist()}
            camera_name = 'robot0_eye_in_hand' if camera == 'wrist' else camera
            before = sim.render(width=1024, height=1024, camera_name=camera_name, depth=True)
            single = render_measurement(env, camera_name, 1024, 1024)
            sitegroup = normal.vopt.sitegroup.copy()
            try:
                normal.vopt.sitegroup[:] = 0
                without_sites = render_measurement(env, camera_name, 1024, 1024)
            finally:
                normal.vopt.sitegroup[:] = sitegroup
            after = sim.render(width=1024, height=1024, camera_name=camera_name, depth=True)
            assert all(np.array_equal(a, b) for a, b in zip(before, after))
            worlds = [_world_from_depth(_metric_depth(pair[1], metadata)[::-1], high)
                for pair in (before, single, without_sites)]
            with np.load(directory/(camera+'_world_high.npz')/(capture+'.npz')) as data:
                old = data[data.files[0]]
            origin = np.asarray(high['extrinsic_cam2world'])[:3, 3]
            direction = worlds[1][v, u]-origin
            length = float(np.linalg.norm(direction))
            geom = np.array([-1], dtype=np.int32)
            ray_distance = mujoco.mj_ray(sim.model._model, sim.data._data, origin,
                direction/length, np.array([0, 1, 0, 0, 0, 0], dtype=np.uint8), 1, -1, geom)
            name = mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, int(geom[0])) if geom[0] >= 0 else None
            samples = sim.model.vis.quality.offsamples
            try:
                sim.model.vis.quality.offsamples = 0
                diagnostic_buffer = mujoco.MjrContext(sim.model._model, mujoco.mjtFontScale.mjFONTSCALE_150)
            finally:
                sim.model.vis.quality.offsamples = samples
            original_buffer = normal.con
            try:
                normal.con = diagnostic_buffer
                segmentation, _ = sim.render(width=1024, height=1024,
                    camera_name=camera_name, depth=True, segmentation=True)
                object_type, object_id = map(int, segmentation[::-1][v, u])
                try:
                    normal.vopt.sitegroup[:] = 0
                    no_sites_seg, _ = sim.render(width=1024, height=1024,
                        camera_name=camera_name, depth=True, segmentation=True)
                finally:
                    normal.vopt.sitegroup[:] = sitegroup
                no_kind, no_id = map(int, no_sites_seg[::-1][v, u])
                no_sites_identity = mujoco.mj_id2name(sim.model._model, no_kind, no_id) if no_id >= 0 else None
                segmentation_name = mujoco.mj_id2name(sim.model._model, object_type, object_id) if object_id >= 0 else None
            finally:
                normal.con = original_buffer
                diagnostic_buffer.free()
                mujoco.mjr_setBuffer(mujoco.mjtFramebuffer.mjFB_OFFSCREEN, original_buffer)
            delta_path = base/'reports'/(case['job']+'_'+args.delta_tag+'.npz')
            with np.load(delta_path) as delta:
                additions = delta['added']
            original_additions = additions.copy()
            if args.include_blockers:
                replay = json.loads(delta_path.with_suffix('.json').read_text())
                screen = replay['stages'][-1]['route_screen']
                blockers = np.asarray([point for points in screen.get('public_scene_collision_points', {}).values()
                    for point in points]).reshape(-1, 3)
                additions = np.unique(np.concatenate([additions, blockers]), axis=0)
            raw_world = old.reshape(-1,3)
            valid_ids = np.flatnonzero(np.isfinite(raw_world).all(axis=1))
            distance, nearest = cKDTree(raw_world[valid_ids]).query(additions)
            matched = distance < 1e-6
            covered_additions.update(np.flatnonzero(matched).tolist())
            added_pixels = []
            for addition, index in zip(additions[matched], valid_ids[nearest[matched]]):
                ay, ax = np.unravel_index(index, old.shape[:2])
                kind, object_id = map(int, no_sites_seg[::-1][ay,ax])
                identity = mujoco.mj_id2name(sim.model._model,kind,object_id) if object_id >= 0 else None
                added_pixels.append({'xyz_m':addition.tolist(),'pixel':[int(ax),int(ay)],
                    'audit_kind': 'membership_addition' if len(original_additions) and
                        np.min(np.linalg.norm(original_additions-addition, axis=1)) < 1e-6 else 'remaining_obstacle',
                    'private_diagnostic_only_identity_without_sites':identity})
            views.append({'new_payload_pixels': added_pixels, 'camera': camera, 'uv': [u, v], 'saved_point_m': old[v, u].tolist(),
                'multisample_point_m': worlds[0][v, u].tolist(), 'single_point_m': worlds[1][v, u].tolist(),
                'saved_to_multisample_m': float(np.linalg.norm(old[v, u]-worlds[0][v, u])),
                'saved_to_single_m': float(np.linalg.norm(old[v, u]-worlds[1][v, u])),
                'private_diagnostic_only_ray': {'geom': name, 'ray_depth_residual_m': ray_distance-length},
                'private_diagnostic_only_pixel_identity': segmentation_name,
                'without_sites_point_m': worlds[2][v, u].tolist(),
                'single_to_without_sites_m': float(np.linalg.norm(worlds[1][v, u]-worlds[2][v, u])),
                'private_diagnostic_only_identity_without_sites': no_sites_identity,
                'policy_rgb_depth_unchanged': True})
        assert len(covered_additions) == len(additions), 'some additions lack a matching camera pixel'
        results.append({'covered_added_pixels': len(covered_additions), 'job': case['job'], 'row': case['row'], 'snapshot': reference,
            'flat_restore_error': error, 'renderer': renderer, 'views': views})
    finally:
        env.close()
        context.free()
report = {'results': results, 'source_commit': 'c916ab1', 'controls': 0,
    'training': False, 'gpu_used': False,
    'scope': 'CPU sensor diagnostic at saved states; no runtime truth or branch outcome',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = args.output
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
