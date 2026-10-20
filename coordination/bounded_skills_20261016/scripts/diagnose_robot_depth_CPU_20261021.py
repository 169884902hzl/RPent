"""Check saved public self pixels against convex and actual hand surfaces."""
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
    p.add_argument('--episode',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source))
    import numpy as np
    from scipy.spatial import cKDTree
    from robots.libero import bounded_robot_depth as module
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from robots.libero.v5_geometric_grasp import panda_geometry
    from robots.libero.bounded_self_filter import public_robot_mask
    raw=pickle.loads((a.episode/'private_initial_physics.pkl').read_bytes())
    obs=raw['actuator_state']['observation_state']['cache']
    robot=measured_robot(SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:obs)))
    import robosuite
    xml=Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'
    geometry=panda_geometry(xml)
    ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
        robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
    row=json.loads(next((a.episode/'loops.jsonl').open()))
    screen=next(d['execution']['screen'] for d in row['execution_details'] if 'execution' in d)
    points=np.array([xyz for group in screen['public_scene_collision_points'].values() for xyz in group])
    triangles={'source_renderer':module.current_robot_triangles(ik,robot,xml)}
    report={'source':str(a.source),'episode':str(a.episode),'private_object_poses_used':False,
        'physics_steps':0,'rpc_calls':0,'cameras':{},
        'renderer_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for camera in ('agentview','wrist'):
        path=a.episode/'episode'/(camera+'_world_high.npz')/'00.npz'
        with np.load(path) as data:world=data['array']
        metadata=json.loads((a.episode/'episode'/(camera+'_metadata.json')/'00.json').read_bytes())
        valid=np.isfinite(world).all(axis=-1)
        pixels=np.flatnonzero(valid);distance,near=cKDTree(world.reshape(-1,3)[pixels]).query(points)
        hit=pixels[near];present=distance<=1e-6
        before=public_robot_mask(world,robot,xml)
        measurements={'world_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'collision_samples_present':int(present.sum()),'static_filter_removed':int(before.reshape(-1)[hit[present]].sum()),'arms':{}}
        for name,faces in triangles.items():
            mask,evidence=module.rendered_robot_mask(world,metadata,faces)
            measurements['arms'][name]={'removed_total':int(mask.sum()),'triangles':len(faces),
                'collision_samples_removed':int(mask.reshape(-1)[hit[present]].sum()),'evidence':evidence}
        report['cameras'][camera]=measurements
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
