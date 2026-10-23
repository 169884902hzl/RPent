from pathlib import Path
import hashlib,json
import numpy as np
root=Path('/public/home/sunyihan/rpent_libero_eval');run=root/'results/bounded_skills/success_feedback_20261024';p=run/'menu9_smoke/case000';old=run/'skills_r2/case005';ref=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def checked(r):
 p=Path(r['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'];return p
x=json.loads((p/'summary.json').read_bytes());assert len(x['trials'])==3
rows=[]
for t in x['trials']:
 a=json.loads(checked(t['record']).read_bytes());b=json.loads((old/f"adaptive_contact_{t['repeat']}/result.json").read_bytes());d=a['preparation_or_skill'];assert a['complete_initial_sha256']==b['complete_initial_sha256']
 request,decision,receipts=d['selected_request'],d['selected_decision'],d['selected_receipts']
 assert request['schema_version']=='bounded-skills/9' and decision['candidate_ids']==[receipts[0]['candidate_id']]
 assert receipts[0]['skill']=='open_close_articulated' and receipts[0]['steps_used']>0
 assert receipts[0]['schema_version']=='bounded-skills/9' and receipts[0]['outcome']=='success'
 assert receipts[0]['stop_reason']=='native_success' and a['native_success']
 aa=np.array([q['action'] for q in d['trace']]);bb=np.array([q['action'] for q in b['preparation_or_skill']['trace']])
 delta=float(np.max(np.abs(aa-bb))) if aa.shape==bb.shape else None
 rows.append({'repeat':t['repeat'],'initial_sha256':a['complete_initial_sha256'],'initial_matches_R2':True,
     'controller_steps':d['steps_used'],'all_skill_steps_including_setup':a['sim_steps'],'wall_s':a['wall_s'],
     'native_success':a['native_success'],'receipt':receipts[0],'controller_action_max_delta_vs_R2':delta,
     'source':t['record']})
o=run/'CPU_menu9_closed';o.mkdir(exist_ok=False);(o/'trials.json').write_text(json.dumps(rows,indent=2)+'\n')
m={'source_tree':x['source_commit'],'states':1,'repeats':3,'native_successes':3,'initial_SHA_matched_R2':3,'controller_steps_each':[r['controller_steps'] for r in rows],
    'action_max_delta_vs_R2':[r['controller_action_max_delta_vs_R2'] for r in rows],
    'raw_summary':ref(p/'summary.json'),'data':ref(o/'trials.json'),'posthoc_selected_train_state_not_a_performance_estimate':True,
    'exact_schema9_menu_and_receipt':True,'no_training':True,'PRO':False,'D2':False,'confirmation':False}
(o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m))
