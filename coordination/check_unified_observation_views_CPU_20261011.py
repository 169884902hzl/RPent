"""Screen two measured target observation routes, without moving the robot."""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, os.environ['GRASP_ROUTE_SOURCE'])
from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand
from robots.libero.v5_grasp_geometry import oblique_box_view
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import sweep_route
from robots.libero.v5_state import Entity

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = ROOT/'coordination/unified_box_observation_views_CPU_20261011_r1'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    ledger = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r6/box/unified/job6857/part0/probe/episodes.jsonl'
    raw = json.loads(ledger.read_text().splitlines()[0])
    first = raw['first_attempt']
    receipt = first['receipt']
    ranking = receipt['geometric_grasp_rankings'][0]
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
    plan = receipt['analytic_grasp_plan']
    entity = Entity(ranking['entity'], 'box', tuple(plan['measured_entity_xyz']),
                    tuple(plan['measured_lower']), tuple(plan['measured_upper']))
    _, axes = np.linalg.eigh(np.cov(target[:, :2].T))
    metadata = json.loads((directory/'wrist_metadata.json/01.json').read_text())
    rows = []
    for sign in (-1, 1):
        view = oblique_box_view(entity, axes[:, 0], position, quat, metadata, sign)
        safe = max(position[2], view['xyz'][2])
        path = [{'phase': 'view_raise', 'xyz': [*position[:2], safe], 'body_quat_xyzw': quat},
                {'phase': 'view_transit', 'xyz': [*view['xyz'][:2], safe],
                 'body_quat_xyzw': view['body_quat_xyzw']},
                {'phase': 'view_measure', 'xyz': view['xyz'],
                 'body_quat_xyzw': view['body_quat_xyzw']}]
        passed, evidence = sweep_route(position, quat, path, scene, np.empty((0, 3)),
                                       geometry, pose_screen=screen)
        rows.append({'view': view, 'route': path, 'passed': passed, 'screen': evidence})
    (OUT/'report.json').write_text(json.dumps({'views': rows, 'private_target_pose_used': False,
        'physical_execution': False, 'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ledger_sha256': hashlib.sha256(ledger.read_bytes()).hexdigest()}, indent=2)+'\n')
    print(json.dumps([{'sign': r['view']['sign'], 'passed': r['passed'],
                       'reason': r['screen'].get('reason')} for r in rows]))


if __name__ == '__main__':
    main()
