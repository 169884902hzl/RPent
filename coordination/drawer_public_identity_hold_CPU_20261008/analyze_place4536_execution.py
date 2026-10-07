"""Verify actual target controls and explicitly indexed public evidence only."""
import argparse
import hashlib
import json
from pathlib import Path


def checked(ref):
    p=Path(ref['path'])
    if hashlib.sha256(p.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError(f'registered evidence changed: {p}')
    return p


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    base=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case0_r2/job4536')
    episode_ref={'path':str(base/'episodes.jsonl'),'sha256':'ba1bc56e9390cb7c0891771fc4e6a2360f688b041e9a87130f3a236b7f4fea0f'}
    row=json.loads(checked(episode_ref).read_text())
    first=row['first_attempt']
    index=Path(row['attempts'][0]['output_dir'])/'place_trace_index.jsonl'
    index_ref={'path':str(index),'sha256':'62567f97a8862bd7a517788c0f9b0a5449049f021455589ede6ffebf90b6240e'}
    refs=[json.loads(l) for l in checked(index_ref).read_text().splitlines() if l]
    files={};frames=[]
    for ref in refs:
        f=json.loads(checked(ref).read_text());files[ref['path']]=ref
        for camera,items in f['cameras'].items():
            for key in ('rgb','world_xyz','camera_metadata'):
                if items.get(key):
                    checked(items[key]);files[items[key]['path']]=items[key]
        for item in f['entities'].values():
            refs_to_check=[*item['perception_evidence'].get('sam_mask_files',{}).values()]
            if item.get('fused_cloud'):
                refs_to_check.append(item['fused_cloud'])
            refs_to_check.extend(v['cloud'] for v in item['per_view'].values() if v.get('cloud'))
            for x in refs_to_check:
                checked(x);files[x['path']]=x
        frames.append({'reference':ref,'robot':f['robot'],'held_offset_m':f['held_offset_m'],
                       'entities':{eid:v['current'] for eid,v in f['entities'].items()}})
    motions=first['motion_evidence']
    counts=[m['executed_action_count'] for m in motions if m.get('name')=='vla_act_chunk']
    assert len(counts)==160 and counts==[5]*160
    assert first['executed_actions']==sum(counts)==800 and first['physically_executed'] is True
    result={'schema':'place4536-original-physical-execution-audit/1','job':4536,
        'episodes':episode_ref,'public_index':index_ref,'status':row['status'],
        'target_selected':first['selected'],'target_complete_chunks':len(counts),
        'target_executed_controls':sum(counts),'target_public_place_verified':first['receipt']['place_verified'],
        'target_private_requested_predicate':first['private_after']['satisfied'],
        'private_label_fields_used':['first_attempt.private_after.satisfied'],
        'private_joint_or_object_geometry_used':False,'infrastructure_failure':row['infrastructure_failure'],
        'case_wall_s':row['case_wall_s'],'public_frames':len(frames),'checked_public_files':list(files.values()),
        'public_files_sha_checked':len(files),'frames':frames,
        'setup_rpent_contact_chunks':sum(s['receipt'].get('chunks',0) for s in row['setup']),
        'setup_executed_actions_counter_scope':'existing counter omits RPent direct chunks; not used as target place evidence',
        'target_controls_exclude_setup':True,'new_qualification':False,'old4311_or4533_scores_changed':False,
        'finding':'r2 uniquely binds a current measured cabinet and executes the original place subtask; one reused development state does not grant qualification'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('job','status','target_selected','target_executed_controls','target_public_place_verified','target_private_requested_predicate','case_wall_s','public_frames','public_files_sha_checked')}))
    print(json.dumps({'report':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))

if __name__=='__main__':
    main()
