"""Audit one shared public predicate on owner-exported DEV rows only."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from collections import Counter
from rpent.skill_package.contract import LEGALITY_VERSION,legal_after
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
base=Path('/home/agilex/cobot_magic/robot_decider_v5r_codex2/benchmarks/bounded_choice/results/legal_alignment_20261018_0750')
results=[]
for name in ('libero_saved_dev_records.jsonl.gz','mujoco_records.jsonl.gz'):
 path=base/name;positions=changed=0;violations=[];errors=[];domains=Counter();timings=[]
 with gzip.open(path,'rt') as stream:
  rows=[json.loads(line) for line in stream]
 for row in rows:
  req=row['request'];label=row['labels']
  for index,pos in enumerate(label['positions']):
   import time
   t=time.perf_counter()
   try:legal=legal_after(req,pos['prefix'])
   except ValueError as e:errors.append(dict(record_id=row['record_id'],position=index,error=str(e)));continue
   timings.append(time.perf_counter()-t);positions+=1;domains[row['scenario']]+=1
   changed+=tuple(pos['legal'])!=legal
   bad=[key for key in ('selected','rule_acceptable') if not (set([pos[key]]) if key=='selected' else set(pos[key]))<=set(legal)]
   if bad:violations.append(dict(record_id=row['record_id'],position=index,fields=bad,legal=list(legal),selected=pos['selected'],acceptable=pos['rule_acceptable']))
 results.append(dict(path=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),requests=len(rows),positions=positions,changed_denominators=changed,violations=violations,prefix_errors=errors,scenarios=dict(domains),max_predicate_s=max(timings),mean_predicate_s=sum(timings)/len(timings)))
report=dict(legality_version=LEGALITY_VERSION,results=results,planner_calls=0,new_observations=0,training=False,confirmation=False,old_rows_modified=False)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert all(not r['violations'] and not r['prefix_errors'] for r in results)
