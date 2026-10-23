"""Register oracle forks/replay from exact retained first-policy endpoints."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
RUN=ROOT/'results/bounded_skills/next_b_pi_first_20261023'
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'

def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

first=json.loads((RUN/'preparation/pi_first24.json').read_text())
endpoints={};reproductions=[]
for i,job in enumerate(first['jobs']):
    candidates=[RUN/f'pi_first24/closed_{i:03d}.json',RUN/f'pi_first24_action_recovery/closed_{i:03d}.json']
    pointer=next(p for p in candidates if p.exists())
    result_ref=json.loads(pointer.read_text());path=Path(result_ref['path']);assert ref(path)==result_ref
    result=json.loads(path.read_text());assert result['retained_endpoint_matches']
    endpoint=result['attempt_endpoint'];assert ref(Path(endpoint['path']))==endpoint
    endpoints[job['case']['name']]=endpoint
    reproductions.append({'case':job['case']['name'],'endpoint':endpoint,'source_result':result_ref,
        'reconstruction':'same-seed pi inference' if pointer==candidates[0] else 'retained actual policy and handoff controls',
        'complete_retained_endpoint_matches':True})
assert len(endpoints)==24
old=BASE/'measured_anchor_2db20013/preparation/D2_recovery1.json'
plan=json.loads(old.read_text());source=ROOT/'source_next_b_eval_4718f24e_20261023'
parent_path=Path(plan['jobs'][0]['manifest']['path']);parent=json.loads(parent_path.read_text())
parent['initial_state_by_case']=endpoints
parent['pi_first_episode_references']=reproductions
parent['initialization_scope']='same retained pi0.5 first-attempt endpoint; remaining total simulation budget preserved; fresh public RGB-D; no private object coordinates in public state'
parent['recovery_budget']=1
parent['training']=False;parent['confirmation']=False
parent_out=RUN/'preparation/pi_first_oracle_parent.json'
with parent_out.open('x') as f:json.dump(parent,f,indent=2)
plan.update(source=str(source),source_commit='4718f24e61851aacd10ee25a0f9818d550b61a53',
    initial_state_by_case=endpoints,pi_first_episode_references=reproductions,
    evaluation_only=True,training=False,confirmation=False,source_revision=ref(source/'SOURCE_REVISION.json'),
    schema=ref(source/'rpent/skill_package/schema.json'))
selected=[]
for job in plan['jobs']:
 if job['case']['name'] in endpoints:
  job['manifest']=ref(parent_out);selected.append(job)
assert len(selected)==24
plan['jobs']=selected
for shard in range(4):
    part=copy.deepcopy(plan);part['jobs']=selected[shard::4]
    path=RUN/f'preparation/pi_first_oracle_{shard}.json'
    with path.open('x') as f:json.dump(part,f,indent=2)
    text=(RUN/'preparation/model_d2_0.sbatch').read_text()
    text=text.replace('nextb-model_d2_0',f'pifirst-oracle-{shard}')
    text=text.replace('model_d2_0.json',f'pi_first_oracle_{shard}.json').replace('/model_d2_0\n',f'/pi_first_oracle_{shard}\n')
    (RUN/f'preparation/pi_first_oracle_{shard}.sbatch').write_text(text)
(RUN/'preparation/pi_first_endpoints.json').write_text(json.dumps({'n':24,'reproductions':reproductions},indent=2))
print(json.dumps({'states':24,'same_seed':sum(r['reconstruction']=='same-seed pi inference' for r in reproductions),
    'retained_action_replay':sum(r['reconstruction']!='same-seed pi inference' for r in reproductions),
    'full_endpoint_matches':24,'jobs':4}))
