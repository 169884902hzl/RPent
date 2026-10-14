"""Release GPUs from superseded development selections, retaining all evidence."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUTPUT = ROOT / 'coordination/latest_contact_priority_interruption_20261009.json'
LATEST = ['4957', '4940', '4942', '4944', '4946', '4948',
          '4951', '4952', '4953', '4954', '4955']


def main():
    if OUTPUT.exists():
        raise ValueError('scheduling change already recorded')
    queue = subprocess.run(['squeue', '-h', '-u', 'sunyihan', '-o', '%i|%T|%N'],
                           check=True, text=True, capture_output=True).stdout
    pending = ['4925', '4950', '4956', '4958', '4959', '4960']
    # Ordering via Nice is ineffective here (all jobs have Priority=1), and
    # scontrol top is denied. Defer our lower-priority selections until the
    # registered critical-path startups finish; no node constraints or holds.
    dependency = 'afterany:' + ':'.join(LATEST)
    deferred = []
    for job in pending:
        if not any(line.startswith(job + '_') and '|PENDING|' in line for line in queue.splitlines()):
            continue
        result = subprocess.run(['scontrol', 'update', 'JobId=' + job,
                                 'Dependency=' + dependency], capture_output=True, text=True)
        result.check_returncode()
        deferred.append(job)
    records = []
    base = ROOT / 'results/harness_v5/perturb_skill_selection_20261009_r1/vla_subtask_bowl/job4924'
    for part in range(1, 8):
        job = f'4924_{part}'
        state = subprocess.run(['squeue', '-h', '-j', job, '-o', '%T|%N'],
                               check=True, capture_output=True, text=True).stdout.strip()
        ledger = base / f'part{part}/probe/episodes.jsonl'
        rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()] if ledger.exists() else []
        records.append({'job': job, 'state_before': state,
            'completed_cases': [row['case']['name'] for row in rows],
            'completed_count': len(rows), 'preserved_output': str(ledger.parent),
            'ledger_sha256_before': hashlib.sha256(ledger.read_bytes()).hexdigest() if ledger.exists() else None,
            'current_uncompleted_trial': 'human_aborted_development_only' if state.startswith('RUNNING|') else None,
            'selection_only': True, 'training_allowed': False,
            'remaining_cases_must_resume': True})
    payload = {'time_pdt': datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
        'reason': 'same-user priorities clipped to 1; top permission denied; latest A3/contact selections first',
        'latest_startups': LATEST, 'deferred_jobs': deferred, 'deferred_dependency': dependency,
        'retained_running_old_jobs': ['4923_0', '4924_0'], 'records': records}
    OUTPUT.write_text(json.dumps(payload, indent=2) + '\n')
    targets = [r['job'] for r in records if r['state_before']]
    if targets:
        subprocess.run(['scancel', *targets], check=True)
    payload['cancel_requested'] = targets
    OUTPUT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(payload), flush=True)


if __name__ == '__main__':
    main()
