"""Explain retained sweep vetoes from their captured public screen geometry."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import pickle
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source))
    import numpy as np
    from scipy.spatial.transform import Rotation
    from scipy.spatial import cKDTree
    old=Path('/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/pi_only_and_approach_20261023')
    result=[]
    for shard in range(3):
        plan=json.loads((old/f'preparation/approach_shard{shard}.json').read_text())
        for index,job in enumerate(plan['jobs']):
            checkpoint=Path(job['branchpoint']['path']);assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==job['branchpoint']['sha256']
            saved=pickle.loads(checkpoint.read_bytes());runtime=saved['public_runtime'];adapter=runtime['adapter']
            path=old/f'approach_shard{shard}_r2/case{index:03d}/elevated_screened.json'
            record=json.loads(path.read_text());evidence=record['motion']['screen']
            key=next(iter(job['component_parameters'].values()))
            choices=[(k,s) for k,s in adapter['_screen_cache'].items() if k[0]==key and k[1] is False]
            origin = 'captured_exact_screen'
            if not choices:
                from types import SimpleNamespace
                from robots.libero.bounded_skills import MeasuredSkillAdapter
                from robots.libero.bounded_offline_labels import FrozenSensors
                from rpent.session import EnvState
                fallback_key, fallback_screen = next(iter(adapter['_screen_cache'].items()))
                robot = {'eef_xyz_m': list(fallback_key[3]), 'eef_quat_xyzw': list(fallback_key[4]),
                    'finger_positions_m': list(fallback_key[5]),
                    'joint_positions_rad': fallback_screen.ik.joints.tolist()}
                depth = object.__new__(EnvState); vars(depth).update(runtime['artifact_state'])
                offline = object.__new__(MeasuredSkillAdapter); vars(offline).update(copy.deepcopy(adapter))
                offline.scene = SimpleNamespace(**copy.deepcopy(runtime['scene']))
                offline.p = SimpleNamespace(env=FrozenSensors(robot, {'used_sim_steps': 0, 'remaining_sim_steps': 10000}))
                offline.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=depth))
                offline.scene.toolkit = offline.ex.toolkit
                offline.record_public_geometry = False
                screen = offline._cloud_and_ik(key, contact=False)
                cache_key = (key, False, None, tuple(robot['eef_xyz_m']),tuple(robot['eef_quat_xyzw']))
                origin = 'reconstructed_from_captured_rgbd_and_proprioception_without_step_or_service'
            else:
                cache_key,screen=choices[-1]
            start={'xyz_m':list(cache_key[3]),'quat_xyzw':list(cache_key[4])}
            site=Rotation.from_quat(start['quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix()
            scene=runtime['scene'];entities=scene['entities'];clouds=scene['measurement_clouds']
            target=entities.get(key)
            entity_trees={k:cKDTree(v) for k,v in clouds.items() if len(v)}
            at=evidence.get('at');pairs=[]
            for kind,field in (('scene','public_scene_collision_points'),('target','public_target_collision_points')):
                for part,hits in evidence.get(field,{}).items():
                    box=next(b for b in screen.geometry['boxes'] if b['name']==part)
                    source_cloud=screen.points if kind=='scene' else screen.target
                    base_local=(source_cloud-np.asarray(start['xyz_m']))@site
                    baseline_distance=screen._halfspace_distance(base_local,box)
                    # Full captured cloud, rather than the old nearest-point IDs.
                    initial_min=float(baseline_distance.min()) if len(baseline_distance) else None
                    for point in hits:
                        point=np.asarray(point);signed_start=float(screen._halfspace_distance(((point-start['xyz_m'])@site)[None],box)[0])
                        at_site=Rotation.from_quat(at['quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix()
                        signed_at=float(screen._halfspace_distance(((point-at['xyz_m'])@at_site)[None],box)[0])
                        matches=[]
                        for identity,tree in entity_trees.items():
                            distance=float(tree.query(point)[0])
                            if distance<=.008:
                                matches.append({'anchor_id':identity,'label':entities[identity].name,
                                    'distance_to_measured_instance_m':distance})
                        matches.sort(key=lambda x:(x['distance_to_measured_instance_m'],x['anchor_id']))
                        table=any(x['label']=='table' for x in matches)
                        category='target' if kind=='target' else 'table' if table else 'other_scene'
                        pairs.append({'hand_part':part,'point_world_m':point.tolist(),'screen_cloud':kind,
                            'captured_screen_point_distance_m': float(cKDTree(source_cloud).query(point)[0]) if len(source_cloud) else None,
                            'classification':category,'target_anchor':key,'target_label':target.name if target else None,
                            'instance_matches':matches,'initial_min_signed_box_clearance_m':initial_min,
                            'this_point_start_signed_box_clearance_m':signed_start,'this_point_rejected_signed_box_clearance_m':signed_at,
                            'increase_in_worst_intrusion_m':initial_min-signed_at if initial_min is not None else None,
                            'start_inside_4mm_margin':initial_min is not None and initial_min<=.004,
                            'retained_start_allowance_min_m':min((screen.initial_margin if kind=='scene' else screen.initial_target_margin).get(part,{}).values(),default=None)})
            result.append({'case':job['case']['name'],'category':job['case']['category'],
                'target_anchor':key,'target_label':target.name if target else None,'initial_pose':start,
                'rejection_pose':at,'old_reason':evidence['reason'],'pairs':pairs,
                'captured_screen_key':str(cache_key),'screen_origin':origin,'branchpoint':job['branchpoint'],
                'screen_geometry_reconstruction':'captured public cache; same point coordinates matched to measured instance clouds',
                'counts_are_capped_by_original_log':'up to 32 saved hit points per hand part',
                'private_truth_used':False})
    a.output.mkdir(parents=True,exist_ok=False)
    data=a.output/'cases.jsonl';data.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in result))
    counts=Counter(p['classification'] for r in result for p in r['pairs'])
    report={'cases':len(result),'point_pairs':sum(len(r['pairs']) for r in result),'classifications':dict(counts),
        'already_in_margin':sum(p['start_inside_4mm_margin'] for r in result for p in r['pairs']),
        'deepening_over_1um':sum(p['increase_in_worst_intrusion_m']>1e-6 for r in result for p in r['pairs'] if p['increase_in_worst_intrusion_m'] is not None),
        'records':{'path':str(data),'sha256':hashlib.sha256(data.read_bytes()).hexdigest()}}
    (a.output/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()
