"""Close same-state ingress forks; distinguish contact evidence from arrival."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--suffix',default='_r2')
    args=parser.parse_args();rows=[]
    for shard in range(3):
        plan=json.loads((args.run/f'preparation/approach_shard{shard}.json').read_text())
        output=args.run/f'approach_shard{shard}{args.suffix}'
        for i,job in enumerate(plan['jobs']):
            pointer=json.loads((output/f'closed_{i:03d}.json').read_text())
            path=Path(pointer['path']);assert ref(path)==pointer
            summary=json.loads(path.read_text());arms=[]
            for arm in summary['arms']:
                record_path=Path(arm['record']['path']);assert ref(record_path)==arm['record']
                record=json.loads(record_path.read_text())
                motion=record['motion']
                unexpected=record['new_or_deeper_nonattached_hand_contacts']
                all_geoms=sorted({name for sample in record['native_contacts']
                    for contact in sample['contacts'] for name in (contact['geom1'],contact['geom2']) if name})
                hand_geoms=[name for name in all_geoms if 'gripper' in name]
                arms.append({'arm':arm['arm'],'initial_physics_sha256':arm['initial_physics_sha256'],
                    'endpoint':arm['endpoint'],'steps_used':motion['steps_used'],
                    'stop_reason':motion['stop_reason'],'endpoint_error_m':motion.get('endpoint_error_m'),
                    'arrived':motion['stop_reason']=='endpoint',
                    'new_or_deeper_nonattached_hand_contact':bool(unexpected),
                    'contact_pairs':unexpected,'initial_contacts':record['initial_hand_contacts'],
                    'initial_grasped_objects':record['initial_dual_finger_objects'],
                    'attached_contact_pairs':record['new_or_deeper_initially_grasped_object_contacts'],
                    'screen_reason':motion['screen'].get('reason'),
                    'screen_passed':motion['screen']['passed'],
                    'native_hand_geoms_seen':hand_geoms,'record':arm['record']})
            assert arms[0]['initial_physics_sha256']==arms[1]['initial_physics_sha256']
            assert arms[0]['endpoint']==arms[1]['endpoint']
            rows.append({'case':summary['case']['name'],'category':summary['case']['category'],
                'old_rejection':job['old_rejection'],'arms':arms,'summary':pointer})
    assert len(rows)==len({r['case'] for r in rows})==30
    groups={}
    for arm in ('straight_no_veto','elevated_screened'):
        data=[next(a for a in r['arms'] if a['arm']==arm) for r in rows]
        groups[arm]={'n':len(data),'arrived':sum(a['arrived'] for a in data),
            'native_contact':sum(a['new_or_deeper_nonattached_hand_contact'] for a in data),
            'arrived_without_contact':sum(a['arrived'] and not a['new_or_deeper_nonattached_hand_contact'] for a in data),
            'not_arrived_without_contact':sum(not a['arrived'] and not a['new_or_deeper_nonattached_hand_contact'] for a in data),
            'zero_step':sum(a['steps_used']==0 for a in data),
            'stops':dict(Counter(a['stop_reason'] for a in data))}
    out=args.run/'CPU_approach30';out.mkdir(exist_ok=False)
    data=out/'paired.jsonl';data.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    report={'groups':groups,'complete_initial_and_endpoint_matches':30,'records':ref(data),
        'selection':plan['selection'],'production_deployed':False,
        'scope':'diagnostic hand-scene contacts; private contacts output only; incomplete unchecked paths cannot certify an old false positive',
        'source_tree':plan['source_commit'],'entry_sha256':plan['entry_sha256'],
        'approach_helper':plan['approach_helper'],'training':False,'evaluation_only':True}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    table=['| 状态 | 直线步数 | 直线到位 | 新/加深接触 | 高位步数 | 高位到位 | 高位停止原因 |',
        '|---|---:|---:|---:|---:|---:|---|']
    for row in rows:
        a,b=row['arms'];table.append(f"| {row['case']} | {a['steps_used']} | {int(a['arrived'])} | {int(a['new_or_deeper_nonattached_hand_contact'])} | {b['steps_used']} | {int(b['arrived'])} | {b['stop_reason']} |")
    (out/'paired_table.md').write_text('\n'.join(table)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
