"""Identify saved public collision pixels; simulator truth is diagnosis only."""
import argparse
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_chunk_v3_self_filter_20261018_b6cf6d0'
sys.path.insert(0, str(source))
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

parser = argparse.ArgumentParser()
parser.add_argument('--open-door', action='store_true')
args = parser.parse_args()
shard, index, task, operation = (140, 3, 35, 'open') if args.open_door else (120, 7, 33, 'close')
base = root / 'results/bounded_skills/feasibility_20261017'
directory = base / f'job8862_{shard}' / f'microwave_{operation}_libero_90_t{task}_s0_oracle_k4'
choices = directory / 'choices.jsonl'
row = json.loads(choices.read_text().splitlines()[index])
reference = row['private_pre_execution_snapshot']
raw = Path(reference['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference['sha256']
saved = pickle.loads(raw)
manifest = base / 'preparation/original20_manifest_chunk_v3_self_filter_20261018.json'
case = json.loads(manifest.read_text())['cases'][shard]
diagnostics = ([attempt['screen'] for item in row['execution_details']
    for attempt in item.get('execution', {}).get('scan_route_attempts', [])]
    if args.open_door else [item for item in row['candidate_screen_diagnostics']
        if item.get('skill') == 'nudge' and item.get('public_scene_collision_points')])
points = np.unique([point for item in diagnostics
    for group in item['public_scene_collision_points'].values() for point in group], axis=0)
assert len(points) > 0
capture = row['public_geometry_evidence']['bounded_screen_None_0_scene']['capture_step']
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
        path = directory / (camera+'_world_high.npz') / (str(capture).zfill(2)+'.npz')
        with np.load(path) as data:
            world = data[data.files[0]]
        meta_path = directory / (camera+'_metadata.json') / (str(capture).zfill(2)+'.json')
        metadata = json.loads(meta_path.read_text())
        origin = np.asarray(metadata['extrinsic_cam2world'])[:3, 3]
        for point in points:
            distances = np.linalg.norm(world-point, axis=2)
            y, x = np.unravel_index(np.nanargmin(distances), distances.shape)
            error = float(distances[y, x])
            if error > 1e-6:
                continue
            direction = point-origin
            length = float(np.linalg.norm(direction))
            identity = np.array([-1], np.int32)
            depth = mujoco.mj_ray(sim.model._model, sim.data._data, origin, direction/length,
                np.array([0, 1, 0, 0, 0, 0], np.uint8), 1, -1, identity)
            geom_id = int(identity[0])
            results.append(dict(camera=camera, pixel=[int(y), int(x)], point_world_m=point.tolist(),
                pixel_residual_m=error, depth_residual_m=float(depth-length) if depth >= 0 else None,
                private_geom=mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
                    if geom_id >= 0 else None,
                private_body=mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_BODY,
                    int(sim.model._model.geom_bodyid[geom_id])) if geom_id >= 0 else None,
                world=dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
                metadata=dict(path=str(meta_path), sha256=hashlib.sha256(meta_path.read_bytes()).hexdigest())))
finally:
    env.close()
report = dict(source_snapshot=str(source), choices=dict(path=str(choices),
    row_index=index, row_sha256=hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()),
    snapshot=reference, restore_max_residual=residual, blocker_points_m=points.tolist(),
    blocked_routes=len(diagnostics), operation=operation, results=results, controls=0, renderer=False, gpu_used=False,
    model_visible=False, used_for_control=False, training=False, confirmation=False,
    scope='private static-state ray identity diagnosis of public collision pixels',
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
output = root / ('coordination/bounded_skills_20261016/reports/'
    + ('microwave8862_open_blocker_private_CPU_20261018.json' if args.open_door
       else 'microwave8862_blocker_private_CPU_20261018.json'))
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(output), blocked_routes=len(diagnostics),
    restore_max_residual=residual,
    results=[{k: row[k] for k in ('camera', 'pixel', 'depth_residual_m', 'private_geom', 'private_body')}
        for row in results])))
