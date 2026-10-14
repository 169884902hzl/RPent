"""Compare common yaw sampling on one saved public box scene, without physics."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, os.environ['GRASP_ROUTE_SOURCE'])
import robots.libero.v5_grasp_route as route
from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand
from robots.libero.v5_grasp_kinematics import PublicPoseScreen

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = ROOT/'coordination/unified_box_common_yaw_CPU_20261011_r1'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    ledger = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r6/box/unified/job6857/part0/probe/episodes.jsonl'
    raw = json.loads(ledger.read_text().splitlines()[0])
    first = raw['first_attempt']
    ranking = first['receipt']['geometric_grasp_rankings'][0]
    directory = Path(raw['output_dir'])
    with np.load(directory/('analytic_target_'+ranking['entity']+'.npz')/'01.npz') as loaded:
        target = loaded[loaded.files[0]]
    clouds = []
    for camera in ('agentview', 'wrist'):
        with np.load(directory/(camera+'_world_high.npz')/'01.npz') as loaded:
            clouds.append(loaded[loaded.files[0]].reshape(-1, 3))
    xml = ROOT/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
    geometry = panda_geometry(str(xml))
    position = first['public_after']['robot']['eef_xyz']
    quat = next(c for c in ranking['candidates'] if c.get('route'))['route'][0]['body_quat_xyzw']
    motion = first['motion_evidence'][-1]
    joints = [joint['qpos'] for joint in motion['final_contact_and_joints']['joints']]
    screen = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', joints, position, quat,
                              geometry['site_offset_in_gripper_m'])
    scene, _ = remove_measured_hand(np.concatenate(clouds), position, quat, geometry,
                                    first['public_after']['robot']['gripper_opening'])
    scene, _ = screen.remove_measured_arm(scene)
    source = Path(route.__file__).read_text()
    old = '(0., math.pi/4, -math.pi/4, math.pi/2)'
    new = '(0., math.pi/4, -math.pi/4, math.pi/2, math.pi/8, -math.pi/8, 3*math.pi/8, -3*math.pi/8)'
    if source.count(old) != 1:
        raise ValueError('common sampler no longer matches recorded source')
    modified = source.replace(old, new)
    (OUT/'experimental_grasp_route.py').write_text(modified)
    exec(compile(modified, str(OUT/'experimental_grasp_route.py'), 'exec'), route.__dict__)
    started = time.monotonic()
    plan, candidates = route.sample_unified_grasps(target, scene, ranking.get('name', 'box'),
        position, quat, geometry, screen, max(position[2], target[:, 2].max()+.15))
    (OUT/'report.json').write_text(json.dumps({'plan': plan, 'candidates': candidates,
        'wall_s': time.monotonic()-started, 'original_feasible': False,
        'private_target_pose_used': False, 'CPU_only': True,
        'physical_success_measured': False,
        'saved_scene_ledger': {'path': str(ledger), 'sha256': hashlib.sha256(ledger.read_bytes()).hexdigest()},
        'experimental_sampler_sha256': hashlib.sha256(modified.encode()).hexdigest()}, indent=2)+'\n')
    print(json.dumps({'plan': plan, 'wall_s': time.monotonic()-started})[:2500])


if __name__ == '__main__':
    main()
