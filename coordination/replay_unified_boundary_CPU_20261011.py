"""Screen fixed saved candidates before/after public instance-boundary repair."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

sys.path.insert(0,os.environ['GRASP_ROUTE_SOURCE'])
from robots.libero.v5_grasp_geometry import complete_instance_boundary, complete_crossview_boundary, complete_planar_boundary
from robots.libero.v5_grasp_route import separate_target_points, sweep_route, approach_route
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
RUN=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r4'
OUT=ROOT/'coordination/unified_boundary_CPU_replay_20261011_r2'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--orient-at-pregrasp',action='store_true')
    parser.add_argument('--crossview', action='store_true')
    parser.add_argument('--planar', action='store_true')
    parser.add_argument('--categories', nargs='+')
    parser.add_argument('--closure-only', action='store_true')
    parser.add_argument('--reuse-passed-ik', action='store_true')
    args=parser.parse_args()
    output_root=args.output
    output_root.mkdir(parents=True,exist_ok=False)
    xml=ROOT/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
    geometry=panda_geometry(str(xml))
    rows=[]
    for category,job in [('bowl',6793),('bottle',6792),('box',6794),('cup',6795),('frypan',6796)]:
        if args.categories and category not in args.categories:
            continue
        ledger=RUN/category/'unified'/f'job{job}/part0/probe/episodes.jsonl'
        raw=json.loads(ledger.read_text().splitlines()[0]);first=raw['first_attempt']
        rankings=first['receipt']['geometric_grasp_rankings'][0]
        directory=Path(raw['output_dir'])
        loaded=np.load(directory/('analytic_target_'+rankings['entity']+'.npz')/'01.npz')
        target=loaded[loaded.files[0]]
        tree=cKDTree(target)
        clouds,completed,details=[],[],[]
        worlds,masks,metas={},{},{}
        for camera in ('agentview','wrist'):
            loaded=np.load(directory/(camera+'_world_high.npz')/'01.npz');world=loaded[loaded.files[0]]
            flat=world.reshape(-1,3)
            near=((flat>=target.min(axis=0)-.00001)&(flat<=target.max(axis=0)+.00001)).all(axis=1)
            mask=np.zeros(len(flat),dtype=bool)
            mask[near]=tree.query(flat[near])[0]<=1e-6
            corrected,evidence=complete_instance_boundary(world,mask.reshape(world.shape[:2]))
            if args.planar:
                corrected,planar=complete_planar_boundary(world,corrected)
                details.append({'camera':camera,**planar})
            worlds[camera],masks[camera]=world,corrected
            metas[camera]=json.loads((directory/(camera+'_metadata.json')/'01.json').read_text())
            clouds.append(flat);completed.append(world[corrected]);details.append({'camera':camera,**evidence})
            np.savez_compressed(output_root/f'{category}_{camera}_boundary.npz',original=mask.reshape(world.shape[:2]),completed=corrected)
        if args.crossview:
            completed=[]
            for camera,other in [('agentview','wrist'),('wrist','agentview')]:
                mask,detail=complete_crossview_boundary(worlds[camera],masks[camera],worlds[other],masks[other],metas[other])
                completed.append(worlds[camera][mask]);details.append({'camera':camera,**detail})
        new_target=np.concatenate(completed)
        candidates=[c for c in rankings['candidates'] if c.get('route_screen')]
        motion=first['motion_evidence'][-1]
        position=first['public_after']['robot']['eef_xyz']
        quat=candidates[0]['route'][0]['body_quat_xyzw']
        joints=[joint['qpos'] for joint in motion['final_contact_and_joints']['joints']]
        screen=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',joints,position,quat,geometry['site_offset_in_gripper_m'])
        cloud,_=remove_measured_hand(np.concatenate(clouds),position,quat,geometry,first['public_after']['robot']['gripper_opening'])
        cloud,_=screen.remove_measured_arm(cloud)
        new_target,obstacles=separate_target_points(new_target,cloud)
        changes=[]
        for candidate in candidates:
            if args.closure_only and candidate['route_screen'].get('reason') != 'closure_sweep_collision':
                continue
            if args.orient_at_pregrasp and candidate['approach']=='top':
                continue
            path=(approach_route(position,quat,candidate['xyz'],candidate['body_quat_xyzw'],
                candidate['approach'],candidate['approach_xyz'],candidate['route'][0]['xyz'][2],
                orient_at_pregrasp=True) if args.orient_at_pregrasp else candidate['route'])
            check_screen=screen
            if args.reuse_passed_ik:
                if args.orient_at_pregrasp or candidate['route_screen'].get('reason') != 'closure_sweep_collision':
                    raise ValueError('saved IK only applies to unchanged, fully passed approach routes')
                cache=[]
                start=np.asarray(position);previous=Rotation.from_quat(quat)
                for waypoint,segment in zip(path,candidate['route_screen']['segments']):
                    end=np.asarray(waypoint['xyz']);desired=Rotation.from_quat(waypoint['body_quat_xyzw'])
                    interpolate=Slerp([0.,1.],Rotation.from_matrix([previous.as_matrix(),desired.as_matrix()]))
                    for ik in segment['ik_checks']:
                        fraction=ik['fraction']
                        if not ik['solution_found']:raise ValueError('old IK did not pass')
                        cache.append((start+fraction*(end-start),interpolate(float(fraction)).as_quat(),ik))
                    start,previous=end,desired
                class SavedIK:
                    def check(self,xyz,orientation):
                        for old_xyz,old_quat,old in cache:
                            if (np.allclose(xyz,old_xyz,atol=1e-12,rtol=0)
                                    and np.allclose(orientation,old_quat,atol=1e-12,rtol=0)):
                                return {**old,'reused_exact_saved_pose':True}
                        raise ValueError('changed pose cannot reuse saved IK')
                check_screen=SavedIK()
            valid,evidence=sweep_route(position,quat,path,obstacles,new_target,geometry,pose_screen=check_screen)
            changes.append({'candidate':candidate['id'],'old_reason':candidate['route_screen'].get('reason'),
                            'new_pass':valid,'new_screen':evidence})
        output=output_root/f'{category}_candidate_pairs.json'
        output.write_text(json.dumps(changes,indent=2)+'\n')
        row={'category':category,'registered_state_sha256':raw['registered_state_sha256'],
             'old_pass':0,'new_pass':sum(c['new_pass'] for c in changes),
             'screened_candidates':len(changes),'views':details,
             'candidate_pairs':str(output),'private_target_pose_used':False,
             'robot_pose_source':'logged_proprioceptive_values_in_motion_diagnostic',
             'start_xyz_and_opening_source':'public_after_before_diagnostic_hold',
             'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest()}
        rows.append(row)
        (output_root/'manifest.json').write_text(json.dumps({'states':rows,'CPU_route_screen_only':True,
            'physical_grasp_success_measured':False,'training_allowed':False,
            'orient_at_pregrasp':args.orient_at_pregrasp,
            'crossview':args.crossview,
            'planar':args.planar,
            'closure_only':args.closure_only,'reuse_passed_ik':args.reuse_passed_ik,
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
        print(json.dumps(row),flush=True)


if __name__=='__main__':main()
