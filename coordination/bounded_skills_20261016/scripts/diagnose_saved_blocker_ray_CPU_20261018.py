"""Privately label exact saved RGB-D blockers without controls or rendering."""
# ruff: noqa: E402 -- select CPU and immutable source before simulator imports
import argparse
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--job', required=True)
parser.add_argument('--row', type=int, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--skill', default='carry_to')
parser.add_argument('--target', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = next((root/f'results/bounded_skills/feasibility_20261017/job{args.job}').glob('*oracle*'))
captured = (directory/'choices.jsonl').read_bytes()
row = json.loads(captured.splitlines()[args.row])
ref = row['private_pre_execution_snapshot']
raw = Path(ref['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == ref['sha256']
saved = pickle.loads(raw)
plan = json.loads(args.manifest.read_text())
case = next(c for c in plan['cases'] if c['name']+'_oracle_k4' == directory.name)
block = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == args.skill
    and d.get('parameters', {}).get('target_id') == args.target)
if 'obstacle_point' in block:
    points = [block['obstacle_point']]
else:
    points = [p for group in block['public_scene_collision_points'].values() for p in group]
points = np.unique(points, axis=0)
step = row['public_geometry_evidence'][f'bounded_screen_{args.target}_0_scene']['capture_step']
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(case['episode']['seed'])
env.reset()
results = []
try:
    env.set_init_state(saved['sim_state'])
    restore_actuators(env, saved['actuator_state'])
    sim = env.env.sim
    residual = float(np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])))
    assert residual < 1e-8
    for camera in ('agentview', 'wrist'):
        meta = json.loads((directory/(camera+'_metadata.json')/f'{step:02d}.json').read_text())
        with np.load(directory/(camera+'_world_high.npz')/f'{step:02d}.npz') as z:
            world = z[z.files[0]]
        transform = np.asarray(meta['extrinsic_cam2world'])
        origin, rotation = transform[:3, 3], transform[:3, :3]
        k = np.asarray(meta['intrinsic_K'])*4
        for point in points:
            flat = np.linalg.norm(world-point, axis=2)
            y, x = np.unravel_index(np.argmin(flat), flat.shape)
            if flat[y, x] > 1e-6:
                continue
            local = (point-origin)@rotation
            corrected = point+rotation@[.5*local[2]/k[0, 0], .5*local[2]/k[1, 1], 0.]
            direction = corrected-origin
            length = float(np.linalg.norm(direction))
            direction /= length
            identity = np.array([-1], np.int32)
            depth = mujoco.mj_ray(sim.model._model, sim.data._data, origin, direction,
                np.array([0, 1, 0, 0, 0, 0], np.uint8), 1, -1, identity)
            model = sim.model._model
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(identity[0])) if identity[0] >= 0 else None
            body = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY,
                int(model.geom_bodyid[identity[0]])) if identity[0] >= 0 else None
            results.append({'camera': camera, 'pixel_xy': [int(x), int(y)],
                'public_point_m': point.tolist(), 'private_visual_geom': name, 'private_body': body,
                'private_depth_minus_public_m': float(depth-length)})
finally:
    env.close()
assert results, 'No exact saved-camera pixel matched the reported blockers'
report = {'scope': 'private saved-pixel ray diagnosis only;zero controls/no renderer',
    'gpu_used': False, 'training': False, 'model_visible': False, 'used_for_control': False,
    'snapshot': ref, 'restore_max_residual': residual, 'source': str(args.source),
    'row': args.row, 'capture_step': step,
    'choices_prefix_sha256': hashlib.sha256(b'\n'.join(captured.splitlines()[:args.row+1])).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'results': results}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
