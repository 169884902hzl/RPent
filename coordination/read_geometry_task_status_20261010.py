"""Read only the registered geometry task jobs and completed method reports."""
from collections import Counter
import datetime
import json
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
jobs = set()
preparations = []
bases = [ROOT / ('results/harness_v5/geometric_grasp_selection_20261010_'+version)
         for version in ('r7','r8','r9','r10','r11','r12','r13')]
bases.append(ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1')
for base in bases:
    for path in base.glob('*/preparation/submission.json'):
        prep = path.parent
        if (prep/'superseded_submission.json').exists():continue
        d = json.loads(path.read_text());jobs.add(d['startup_job'].split(';')[0])
        preparations.append(str(prep))
        formal = prep/'formal_submission.json'
        if formal.exists():jobs.add(json.loads(formal.read_text())['formal_job'].split(';')[0])
status = subprocess.check_output(['sacct','-X','-n','-P','-j',','.join(sorted(jobs)),
    '-o','JobID,State,ExitCode'],text=True)
rows = [l.split('|') for l in status.splitlines() if l.strip()]
queue = subprocess.check_output(['squeue','-r','-u','sunyihan','-h','-o','%i|%T|%N|%j'],text=True)
active = [l.split('|') for l in queue.splitlines() if l.strip() and l.split('|')[0].split('_')[0] in jobs]
closed = []
progress = []
for prep in preparations:
    parent = Path(prep).parent
    counts = []
    for path in parent.glob('job*/part*/probe/infrastructure_status.json'):
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        counts.append(value)
    progress.append({'group': parent.parent.name + '/' + parent.name,
        'recorded_n': sum(value.get('shard_completed_cases', 0) for value in counts),
        'infrastructure_cases': sum(value.get('infrastructure_cases', 0) for value in counts)})
event = ROOT/'coordination/geometric_methods_event_closed_20261010_r1'
for path in sorted(event.glob('*/publication.json')):
    report = json.loads((path.parent/'manifest.json').read_text())
    group,value = next(iter(report['groups'].items()))
    m = value['v3_success_observed_denominator']
    closed.append({'group':group,'v3_k':m['k'],'registered_n':value['registered_n'],
        'agreement_k':value['v3_public_verifier']['agreement_all_registered']['k']})
print(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'registered_job_count':len(jobs),'method_count':len(preparations),
    'active_counts':dict(Counter(r[1] for r in active)),
    'progress': progress,
    'running':[r[:3] for r in active if r[1]=='RUNNING'],
    'failures':[r[:3] for r in rows if r[1] in ('FAILED','TIMEOUT','CANCELLED','NODE_FAIL','OUT_OF_MEMORY')],
    'closed':closed}))
