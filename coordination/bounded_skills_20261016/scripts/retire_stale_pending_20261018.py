"""Retire only unstarted ordinary-pending stale-source development shards."""
import json
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path('/public/home/sunyihan/rpent_libero_eval')
base=root/'coordination/bounded_skills_20261016'
rows=[s.split('|') for s in subprocess.check_output(['squeue','-r','-h','-u','sunyihan','-o','%i|%j|%T|%R|%N'],text=True).splitlines()]
selected=[r for r in rows if r[0].split('_')[0] in {'8870','8987'} and r[2]=='PENDING' and 'JobHeld' not in r[3]]
for r in selected:
 assert r[1]=='rd-bounded-feasibility-v21', r
 directory=root/'results/bounded_skills/feasibility_20261017'/('job'+r[0])
 assert not list(directory.glob('*/choices.jsonl')), str(directory)
report=dict(time_pacific=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
 reason='Known v3 contact-identity / precontact-surface defects; use startup-gated corrected source after the focused pairs',
 selected=selected,running_untouched=[r for r in rows if r[2]=='RUNNING'],
 held_untouched=True, protected_jobs_modified=False, no_physical_records_in_selected=True)
path=base/'reports/stale_pending_retirement_20261018.json'
assert not path.exists()
path.write_text(json.dumps(report,indent=2)+'\n')
if selected:
 subprocess.run(['scancel',*[r[0] for r in selected]],check=True)
report['queue_after']=[s.split('|') for s in subprocess.check_output(['squeue','-r','-h','-u','sunyihan','-o','%i|%j|%T|%R|%N'],text=True).splitlines() if s.split('|')[0].split('_')[0] in {'8870','8987'}]
report['cancelled_count']=len(selected)
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(cancelled_count=len(selected),receipt=str(path))))
