"""Close the registered pi-default mode against the same pi/model/oracle cohort."""
import argparse
import json
from pathlib import Path
from close_next_b_pi_first_CPU_20261023 import read_ref, score

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-incomplete',action='store_true');a=p.parse_args()
baseline=a.run/'CPU_model_closed'
rows=[json.loads(s) for s in (baseline/'paired_cases.jsonl').read_text().splitlines()]
original=[json.loads(s) for s in (baseline/'original6.jsonl').read_text().splitlines()]
prior={r['case']:r for r in rows};prior.update({r['arm_id']:r for r in original})
measured={};pending=[]
for stage in ('pi_default_d2_0','pi_default_d2_1','pi_default_d2_2','pi_default_original6'):
    plan=json.loads((a.run/f'preparation/{stage}.json').read_text())
    for i,job in enumerate(plan['jobs']):
        key=job['case']['name']+(f"_K{job['k']}" if stage.endswith('original6') else '')
        pointer=a.run/stage/f'closed_{i:03d}.json'
        if not pointer.exists():pending.append(key);continue
        report,raw=read_ref(json.loads(pointer.read_text()))
        assert report['status']=='physical_result' and report['human_available'] is False and report['oracle_choices_used']==0
        assert report['initial_snapshot']['physics_sha256']==prior[key]['initial_physics_sha256']
        assert report['model_service']['selection_policy']=={'version':'pi-whole-task-margin/1','enabled':True,'delta':2.0}
        assert report['model_service']['adapter_sha256']=='5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26'
        measured[key]={k:report[k] for k in ('success','decisions','sim_steps','skill_sim_steps','stop_reason','wall_s','wall_time_breakdown','initial_snapshot','model_service')}
        measured[key]['raw']=raw
if not a.allow_incomplete:assert not pending,pending
for row in rows+original:
    key=row.get('case',row.get('arm_id'));row['pi_default_success']=measured.get(key,{}).get('success');row['pi_default']=measured.get(key)
manifest={'D2':score([r['pi_default_success'] for r in rows]),'original6':score([r['pi_default_success'] for r in original]),
    'closed_arms':len(measured),'pending':pending,'human_available':False,'recovery_budget':1,
    'complete_initial_state_matches':len(measured),'source_tree':'4718f24e61851aacd10ee25a0f9818d550b61a53',
    'selection_policy':{'version':'pi-whole-task-margin/1','enabled':True,'delta':2.0},
    'comparison_caveat':'registered C2 mode uses next-a weights, fixed training-selected delta2 and legal5; not next-b plus a threshold',
    'training':False,'evaluation_only':True}
a.output.mkdir(parents=True,exist_ok=False)
for name,data in (('paired_cases',rows),('original6',original)):
    (a.output/f'{name}.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in data))
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
table=['| 场景 | 只用π | 旧模型A | 新模型B | π默认模式 | 开局oracle |', '|---|---:|---:|---:|---:|---:|']
for r in rows:
    table.append('| '+r['case']+' | '+' | '.join('?' if r[k] is None else str(int(r[k])) for k in ('pi_only_success','v_next_a_success','v_next_b_success','pi_default_success','oracle_from_start_success'))+' |')
(a.output/'paired_table.md').write_text('\n'.join(table)+'\n')
print(json.dumps(manifest))
