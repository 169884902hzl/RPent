"""Freeze stratified distinct-state ingress diagnostics from the retained audit."""
import copy
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
RUN = ROOT/'results/bounded_skills/pi_only_and_approach_20261023'

def ref(p):
    return {'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

master_path = BASE/'measured_anchor_efa57340/preparation/all155.json'
master = json.loads(master_path.read_text())
cases = {j['case']['name']:j['case'] for j in master['jobs']}
audit = BASE/'measured_anchor_efa57340/CPU_155_audit_r1/trials.jsonl'
eligible = [r for r in map(json.loads,audit.read_text().splitlines())
    if r.get('last_preparation_failure')=='measured_sweep_collision'
    and r['after_steps']==0 and len(r['preparation_events'])==1]
unique = {}
for row in sorted(eligible,key=lambda r:(r['case'],r['seed'])):
    unique.setdefault(row['case'],row)
groups = defaultdict(deque)
for row in unique.values():groups[row['category']].append(row)
selected = []
while len(selected)<30:
    for category in sorted(groups):
        if groups[category] and len(selected)<30:selected.append(groups[category].popleft())
plan = copy.deepcopy(master)
plan.update(source=str(ROOT/'source_measured_progress_2db20013_20261023'),
    source_commit='2db200134ea6689e36a66e8aee6f45daa8270b4e',
    source_revision=ref(ROOT/'source_measured_progress_2db20013_20261023/SOURCE_REVISION.json'),
    entry_sha256=ref(ROOT/'run_approach_forks_20261023.py')['sha256'],
    approach_helper=ref(ROOT/'bounded_approach.py'), training=False, confirmation=False,
    selection={'rule':'round-robin sorted categories, lexical distinct case, lowest retained trial seed',
        'eligible_trials':len(eligible),'eligible_states':len(unique),'selected_states':30,
        'counts':dict(Counter(r['category'] for r in selected)),
        'sampling_limitation':'stratified rejected diagnostic states; not a random estimate of all candidates'},
    parent_master=ref(master_path),parent_audit=ref(audit),jobs=[])
for row in selected:
    case = cases[row['case']]
    component = row['preparation_events'][0]['skill']
    assert component in ('move_to','carry_to')
    params = ({'anchor_id':row['source_public_id']} if component=='move_to'
        else {'target_id':row['target_public_id']})
    branch = Path(row['after']['path']).parent/'episode/private_branchpoint.pkl'
    plan['jobs'].append({'case':case,'old_rejection':row,'branchpoint':ref(branch),
        'component_skill':component,'component_parameters':params})
for shard in range(3):
    part = copy.deepcopy(plan);part['jobs']=plan['jobs'][shard::3]
    target = RUN/f'preparation/approach_shard{shard}.json'
    with target.open('x') as f:json.dump(part,f,indent=2)
    job = (RUN/'preparation/pi_only_shard0.sbatch').read_text()
    job = job.replace('rd-c3-s6-v7-pionly-0',f'rd-c3-s6-v7-approach-{shard}')
    job = job.replace('run_pi_only_closedloop_20261023.py','run_approach_forks_20261023.py')
    job = job.replace('pi_only_shard0.json',f'approach_shard{shard}.json')
    job = job.replace('/pi_only_shard0 ',f'/approach_shard{shard} ')
    job = job.replace(' --episode-concurrency 8','')
    job = job.replace('export PI05_CHECKPOINT_PATH=', 'export SAM3_CHECKPOINT_PATH='+str(ROOT/'assets/sam3/sam3.pt')+'\nexport PI05_CHECKPOINT_PATH=')
    (RUN/f'preparation/approach_shard{shard}.sbatch').write_text(job)
with (RUN/'preparation/approach30.json').open('x') as f:json.dump(plan,f,indent=2)
print(json.dumps(plan['selection']))
