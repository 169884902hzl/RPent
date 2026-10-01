"""Compare an explicit paired subset of D2 development episodes only."""
import argparse
from pathlib import Path
import json
from collections import Counter

ap=argparse.ArgumentParser()
ap.add_argument('--before',type=Path,required=True)
ap.add_argument('--after',type=Path,required=True)
ap.add_argument('--manifest',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
before=json.loads(a.before.read_text());after=json.loads(a.after.read_text())
key=lambda r:(r['episode']['suite'],r['episode']['task'],r['episode']['seed'])
b={key(r):r for r in before};c={key(r):r for r in after}
selected=json.loads(a.manifest.read_text())['episodes']
pairs=[]
for e in selected:
 k=(e['suite'],e['task'],e['seed'])
 if k not in c:continue
 old=b[k];new=c[k]
 pairs.append({'episode':e,'before_physical_success':old['physical_success'],'after_physical_success':new['physical_success'],'before_terminal':old['primary_terminal'],'after_terminal':new['primary_terminal'],'before_secondary':old['secondary_flags'],'after_secondary':new['secondary_flags'],'before_hashes':old['hashes'],'after_hashes':new['hashes']})
s={'purpose':'paired_development_diagnostic_not_Table_A','planned':len(selected),'completed_pairs':len(pairs),'before_physical_success':sum(r['before_physical_success'] for r in pairs),'after_physical_success':sum(r['after_physical_success'] for r in pairs),'before_terminal_counts':dict(Counter(r['before_terminal'] for r in pairs)),'after_terminal_counts':dict(Counter(r['after_terminal'] for r in pairs)),'pairs':pairs}
a.output.write_text(json.dumps(s,indent=2));print(json.dumps({k:v for k,v in s.items() if k!='pairs'},indent=2))
