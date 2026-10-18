"""Insert a startup, then paired v2/legacy-boundary originals in GPU lane 3."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--full', action='store_true')
parser.add_argument('--tag', default='chunk_v2_20261018')
parser.add_argument('--replace-array', action='append', default=[])
parser.add_argument('--indices', default='0-219', help='Registered original-state indices for the paired full run')
args = parser.parse_args()
indices = []
for part in args.indices.split(','):
    ends = [int(value) for value in part.split('-')]
    assert len(ends) in {1, 2}
    indices.extend(range(ends[0], ends[-1]+1))
assert indices and len(indices) == len(set(indices)) and all(0 <= i < 220 for i in indices)
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
mode = 'full' if args.full else 'startup'
receipt = base/'reports'/f'{args.tag}_{mode}_submission.json'
assert not receipt.exists(), 'Use the existing submission receipt'
prep = json.loads((base/'reports'/f'{args.tag}_preparation.json').read_text())
source, manifest = Path(prep['snapshot']), Path(prep['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == prep['manifest']['sha256']
launcher = source/'scripts/run_bounded_21f0744_20261017.sbatch'
assert all(p.is_absolute() and p.is_file() for p in (launcher, manifest))
startup_proof = None
if args.full:
    startup = json.loads((base/'reports'/f'{args.tag}_startup_submission.json').read_text())
    job = startup['job']+'_24'
    directory = root/'results/bounded_skills/feasibility_20261017'/('job'+job)
    rows = [json.loads(line) for line in (directory/'episodes.jsonl').open()]
    assert len(rows) == 1 and rows[0]['status'] == 'startup_physical'
    physical = json.loads(next(directory.glob('*oracle*/first_physical_request.json')).read_text())
    assert physical['sim_steps'] > 0
    state = subprocess.check_output(['sacct','-X','-n','-j',job,'--format=State,ExitCode','-P'],text=True).strip()
    assert state == 'COMPLETED|0:0', state
    startup_proof = {'job':job,'summary':rows[0],'first_physical_request':physical,'state_exit':state}
raw = subprocess.check_output(['squeue','-r','-h','-u','sunyihan','-o','%i|%j|%T|%N|%R|%b'],text=True)
codex2_gpu = [line for line in raw.splitlines()
    if line.split('|')[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
    and 'gpu' in line.split('|')[5].lower() and line.split('|')[2] in {'RUNNING','PENDING'}]
aggregate_cap = 3 if codex2_gpu else 4
ours = [line.split('|') for line in raw.splitlines() if '|rd-bounded-' in line and 'rd-bounded-choice-' not in line]
running = [row for row in ours if row[2] == 'RUNNING']
assert len(running) <= 4 and all(row[3]=='node02' for row in running), running
# Do not touch held jobs, c5/c6/rf, or Codex2's model jobs.
active = [row[0] for row in running]
lane_arrays = ({'8173', '8192', '8252', '8265'} | set(args.replace_array)) if args.full else {'8173'}
following = [row[0] for row in ours if row[0].split('_')[0] in lane_arrays
    and row[2]=='PENDING' and 'JobHeld' not in row[4]]
capacity = max(1, aggregate_cap-len(running)) if args.full else 1
if args.full:
    dependency = ('?'.join('afterany:'+child for child in active)
                  if len(running) >= aggregate_cap else 'afterany:'+startup_proof['job'])
else:
    dependency = ('?'.join('afterany:'+child for child in active)
                  if len(running) >= aggregate_cap else None)
arguments = ['sbatch','--parsable','--nodelist=node02','--nice=500',
    '--array='+(args.indices+'%'+str(capacity) if args.full else '24%1'),
    *(['--dependency='+dependency] if dependency else []),
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+prep['source_commit']+',MANIFEST='+str(manifest)
        +',STARTUP='+('0' if args.full else '1')+',PAIR_LEGACY='+('1' if args.full else '0'),str(launcher)]
job = subprocess.check_output(arguments,text=True).strip().split(';')[0]
receipt.write_text(json.dumps({'job': job, 'mode': mode, 'arguments': arguments,
    'source_commit': prep['source_commit'], 'snapshot': str(source),
    'manifest': prep['manifest'], 'submission_updates_complete': False}, indent=2)+'\n')
updates=[]
for child in following:
    # Preserve old serial lane successors: 8192 -> 8252, 8262 -> 8265.
    # All full-v2 shards finish before these older ordinary pending jobs run.
    previous = {'8252': '8192', '8265': '8262'}.get(child.split('_')[0]) if args.full else None
    dependency = 'afterany:'+job+(':'+previous if previous else '')
    command=['scontrol','update','JobId='+child,'Dependency='+dependency]
    subprocess.run(command,check=True)
    updates.append(command)
report={'job':job,'mode':mode,'arguments':arguments,'source_commit':prep['source_commit'],
    'snapshot':str(source),'manifest':prep['manifest'],'following_updates':updates,'queue_before':ours,
    'lane':'available_node02' if args.full else 3,'aggregate_cap':aggregate_cap,
    'codex2_gpu_jobs':codex2_gpu,'startup_proof':startup_proof,'training':False,'confirmation':False,
    'indices': indices if args.full else [24],
    'scope':'original-task oracle upper bound and matched boundary-rule comparison; no pi05',
    'submission_updates_complete':True}
receipt.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ('job','mode','source_commit','snapshot','lane')}))
