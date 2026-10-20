"""Recheck fixed10's first-chunk blockers against matching public captures."""
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--panel',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source.resolve(strict=True)))
    import numpy as np
    import robosuite
    from scipy.spatial import cKDTree
    from robots.libero import bounded_robot_depth as depth
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from robots.libero.v5_geometric_grasp import panda_geometry

    xml=Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'
    geometry=panda_geometry(xml);rows=[]
    for case in sorted(a.panel.glob('case[0-9][0-9][0-9]')):
        initial=pickle.loads((case/'private_initial_physics.pkl').read_bytes())
        obs=initial['actuator_state']['observation_state']['cache']
        robot=measured_robot(SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:obs)))
        line=next((case/'loops.jsonl').open('rb'))
        loop=json.loads(line);capture=0
        for detail in loop['execution_details']:
            if 'execution' not in detail:continue
            execution=detail['execution'];screen=execution.get('screen',{})
            # Schema6 move/contact steps each finish with exactly one refresh.
            # This audit only uses the first chunk and verifies its fresh
            # receipt capture before associating the preceding RGB-D frame.
            receipt=next(r for r in loop['receipts'] if r['candidate_id']==detail['candidate_id'])
            fresh=[e['capture_step'] for e in receipt['evidence']]
            if fresh and max(fresh)!=capture+1:
                raise ValueError('unexpected fixed10 capture schedule')
            if screen and not screen['passed']:
                samples=[]
                for key in ('public_scene_collision_points','public_target_collision_points'):
                    samples.extend(xyz for group in screen.get(key,{}).values() for xyz in group)
                arm=screen.get('arm_screen',{}).get('obstacle_point')
                if arm is not None:samples.append(arm)
                points=np.asarray(samples,float).reshape(-1,3)
                ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
                    robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
                faces=depth.current_robot_triangles(ik,robot,xml)
                record={'case':case.name,'candidate_id':detail['candidate_id'],'skill':receipt['skill'],
                    'reason':screen['reason'],'capture_step':capture,'samples':len(points),
                    'public_robot':robot,'loop_line_sha256':hashlib.sha256(line).hexdigest(),'cameras':{}}
                for camera in ('agentview','wrist'):
                    path=case/'episode'/(camera+'_world_high.npz')/f'{capture:02d}.npz'
                    with np.load(path) as data:world=data['array']
                    metadata=json.loads((case/'episode'/(camera+'_metadata.json')/f'{capture:02d}.json').read_bytes())
                    valid=np.flatnonzero(np.isfinite(world).all(axis=-1))
                    mask,evidence=depth.rendered_robot_mask(world,metadata,faces)
                    if len(points):
                        distances,near=cKDTree(world.reshape(-1,3)[valid]).query(points)
                        present=distances<=1e-6
                        removed=int(mask.reshape(-1)[valid[near[present]]].sum())
                    else:present=np.empty(0,bool);removed=0
                    record['cameras'][camera]={'capture_path':str(path),
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'present_samples':int(present.sum()),'self_samples_removed':removed,
                        'filter':evidence}
                rows.append(record)
            if execution.get('trace'):
                robot=execution['trace'][-1]['after']
            capture+=1
    report={'rows':rows,'physics_steps':0,'rpc_calls':0,'private_object_coordinates_used':False,
        'scope':'same first-chunk blocker samples and matching RGB-D/proprioception; not physical collision truth',
        'renderer_sha256':hashlib.sha256(Path(depth.__file__).read_bytes()).hexdigest()}
    with a.output.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({'rows':len(rows),'output':str(a.output)}),flush=True)


if __name__=='__main__':main()
