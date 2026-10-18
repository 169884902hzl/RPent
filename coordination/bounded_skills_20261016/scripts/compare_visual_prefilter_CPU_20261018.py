"""Pair unchanged mesh tests on exact saved public clouds; no GPU or controls."""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--candidate-file', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np

from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


baseline = module('baseline_visual_filter', args.source/'robots/libero/bounded_self_filter.py')
candidate = module('candidate_visual_filter', args.candidate_file)
root = Path('/public/home/sunyihan/rpent_libero_eval')
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = panda_geometry(xml)
results = []
for job, index, step in [('9000_24',0,0),('8870_3',2,4),('8870_2',2,5),('8862_60',0,0)]:
    directory, = [d for d in (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*')
        if not d.name.endswith('_legacy')]
    raw = (directory/'choices.jsonl').read_bytes()
    rows = [json.loads(s) for s in raw.splitlines()]
    if index == 0:
        robot = next(c['before'] for d in rows[0]['execution_details']
            for c in d.get('execution', {}).get('trace', []))
    else:
        robot = next(c['after'] for row in reversed(rows[:index]) for d in reversed(row['execution_details'])
            for c in reversed(d.get('execution', {}).get('trace', [])))
    assert robot['eef_xyz_m'] == rows[index]['request']['robot']['eef_xyz_m']
    ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
        robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
    for camera in ('agentview','wrist'):
        path = directory/(camera+'_world_high.npz')/f'{step:02d}.npz'
        with np.load(path) as archive:
            cloud = archive[archive.files[0]].reshape(-1,3)
        timings = {'baseline':[], 'candidate':[]}
        outputs = {}
        for repeat in range(4):
            methods = [('baseline',baseline),('candidate',candidate)]
            if repeat % 2:
                methods.reverse()
            for name, implementation in methods:
                start = time.perf_counter()
                outputs[name] = implementation.remove_visual_robot(cloud,ik)
                elapsed = time.perf_counter()-start
                if repeat:
                    timings[name].append(elapsed)
            np.testing.assert_array_equal(outputs['baseline'][0],outputs['candidate'][0])
            assert outputs['baseline'][1] == outputs['candidate'][1]
        results.append(dict(job=job,row=index,camera=camera,capture_step=step,
            choices_sha256=hashlib.sha256(raw).hexdigest(),cloud_path=str(path),
            cloud_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_points=len(cloud),
            output_sha256=hashlib.sha256(outputs['baseline'][0].tobytes()).hexdigest(),
            output_array_exact=True,evidence_exact=True,evidence=outputs['baseline'][1],
            timing_s=timings,median_s={k:float(np.median(v)) for k,v in timings.items()}))
report=dict(results=results,baseline_source=str(args.source),candidate_file=str(args.candidate_file),
    candidate_sha256=hashlib.sha256(args.candidate_file.read_bytes()).hexdigest(),
    controls=0,gpu_used=False,private_truth_used=False,training=False,confirmation=False,
    scope='exact saved public RGB-D visual-self-filter kernels; not full request or episode throughput')
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([dict(job=r['job'],camera=r['camera'],median_s=r['median_s'],exact=True) for r in results]))
