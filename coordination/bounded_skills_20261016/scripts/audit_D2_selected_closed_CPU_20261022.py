from pathlib import Path
from collections import Counter
import json,hashlib,argparse,sys
p=argparse.ArgumentParser();p.add_argument('--view',type=Path,required=True);a=p.parse_args()
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def load(r):
 p=Path(r['path']);assert ref(p)==r;return json.loads(p.read_bytes())
rows=[json.loads(l) for l in (a.view/'aggregate/paired_cases.jsonl').read_text().splitlines()]
bycase=[];unavailable=[];terminal=[]
for row in rows:
 replay=load(row['summary']);sampling=load(replay['parent_summary']) if 'parent_summary' in replay else replay
 item={'case':row['case'],'recovery_budget':row['recovery_budget'],'sampling_summary':ref(Path(replay['parent_summary']['path'])) if 'parent_summary' in replay else row['summary'],'replay_summary':row['summary'],'sampled_path_success':row['sampled_envelope_success'],'full_replay_success':row['success']};bycase.append(item)
 for sub in sampling.get('subtasks',[]):
  for t in sub['trials']:
   if t.get('reason')=='requested_vla_variant_unavailable':
    unavailable.append({'case':row['case'],'budget':row['recovery_budget'],'subtask':sub['subtask']['id'],'variant':t.get('vla_variant'),'source_id':t.get('source_public_id'),'target_id':t.get('target_public_id'),'endpoint':t['endpoint'],'seed':t['trial_seed']})
 if replay['full_replay'] and replay['full_replay'][-1]['success'] and not row['success']:
  terminal.append({'case':row['case'],'budget':row['recovery_budget'],'summary':row['summary']})
(a.view/'audit_input_episodes.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in bycase))
(a.view/'current_unavailable.json').write_text(json.dumps({'n':len(unavailable),'rows':unavailable,'terminal_success_final_false':terminal,'source':'actual closed records; eval only'},indent=2)+'\n')
print(json.dumps({'episodes':len(rows),'unavailable':len(unavailable),'terminal_success_final_false':len(terminal),'unavailable_by_case':dict(Counter(x['case'] for x in unavailable))}))
