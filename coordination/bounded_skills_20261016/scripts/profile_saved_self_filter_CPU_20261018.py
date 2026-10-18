"""Time exact public RGB-D self filtering without simulator or policy calls."""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--candidate-file', type=Path)
parser.add_argument('--episode', type=Path, action='append', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np

from robots.libero.bounded_skills import MeasuredSkillAdapter

source_file = args.source/'robots/libero/bounded_skills.py'
if args.candidate_file:
    source_file = args.candidate_file
    spec = importlib.util.spec_from_file_location('candidate_bounded_skills', source_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MeasuredSkillAdapter = module.MeasuredSkillAdapter

results = []
for episode in args.episode:
    ledger = episode/'choices.jsonl'
    first = ledger.read_bytes().splitlines()[0]
    choice = json.loads(first)
    robot = next(detail['execution']['trace'][0]['before']
        for detail in choice['execution_details'] if detail.get('execution', {}).get('trace'))
    assert robot['eef_xyz_m'] == choice['request']['robot']['eef_xyz_m']
    frames = {}
    inputs = {str(ledger): hashlib.sha256(first).hexdigest()}
    for camera in ('agentview', 'wrist'):
        path = episode/(camera+'_world_high.npz')/'00.npz'
        raw = path.read_bytes()
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        with np.load(path) as stream:
            frames[camera] = stream[stream.files[0]].copy()
    obs = dict(robot0_eef_pos=robot['eef_xyz_m'], robot0_eef_quat=robot['eef_quat_xyzw'],
        robot0_joint_pos=robot['joint_positions_rad'], robot0_gripper_qpos=robot['finger_positions_m'])
    state = SimpleNamespace(latest_step=0,
        load=lambda name: frames[name.removesuffix('_world_high.npz')])
    env = SimpleNamespace(raw_obs=lambda: obs)
    executor = SimpleNamespace(p=SimpleNamespace(env=env), scene=SimpleNamespace(),
        toolkit=SimpleNamespace(_state=state))
    xml = Path('/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')
    adapter = MeasuredSkillAdapter(executor, xml, allow_vla=False)
    # Only establish the common self-filtered raw world; no target planning.
    adapter._contact_pixels = lambda key: np.empty((0, 3))
    screen = adapter._cloud_and_ik()
    artifact = choice['public_geometry_evidence']['bounded_screen_None_0_scene']
    path = Path(artifact['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
    with np.load(path) as stream:
        expected = stream[stream.files[0]]
        assert np.array_equal(screen.points, expected), 'saved scene reconstruction differs'
    calls = []
    for camera, world in frames.items():
        outputs = []
        for repeat in range(4):
            start = time.perf_counter()
            filtered = adapter._self_filtered_world(world)
            elapsed = time.perf_counter()-start
            outputs.append(hashlib.sha256(filtered.tobytes()).hexdigest())
            calls.append(dict(camera=camera, repeat=repeat, wall_s=elapsed,
                shape=list(world.shape), output_sha256=outputs[-1]))
        assert len(set(outputs)) == 1
    results.append(dict(episode=str(episode), inputs=inputs, scene_exactly_reconstructed=True,
        calls=calls, measured_raw_scene_points=len(adapter._base_geometry[0])))
report = dict(source=str(args.source), rows=results,
    scope='CPU same-capture self-filter microbenchmark; no simulation, segmentation or controls',
    source_file=str(source_file), source_sha256=hashlib.sha256(source_file.read_bytes()).hexdigest(),
    training=False, confirmation=False)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps([dict(episode=row['episode'], points=row['measured_raw_scene_points'],
    calls=[dict(camera=c['camera'], wall_s=round(c['wall_s'], 4)) for c in row['calls']])
    for row in results]))
