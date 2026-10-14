"""One owner monitors both public grasp batches and releases passing startups."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASES = [ROOT / 'results/harness_v5/public_servo_coupling_r16_selection_20261010_r1',
         ROOT / 'results/harness_v5/public_physical_hold_r18_selection_20261010_r1',
         ROOT / 'results/harness_v5/servo_only_fiveclass_selection_20261010_r1',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r1',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r2',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r3',
         ROOT / 'results/harness_v5/analytic_failure_phases_selection_20261010_r1',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r4',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r5',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r6',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r8',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r9',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r10',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r11',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r12',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r13',
         ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1',
         ROOT / 'results/harness_v5/grasp_confirmation_startup_resume_20261010_r1']
LOG = ROOT / 'coordination/public_grasp_r16_r18_watch_ledger_20261010.jsonl'
previous = None
reported_failures = set()
while True:
    release = subprocess.run(['python3', str(ROOT / 'coordination/monitor_registered_grasp_v3r9.py')],
                             capture_output=True, text=True)
    if release.returncode:
        print(release.stdout + release.stderr, flush=True)
        raise SystemExit(release.returncode)
    jobs, formal_count, empty_nontrials = [], 0, set()
    preps = [path.parent for base in BASES for path in sorted(base.glob('*/preparation/submission.json'))
             if not (path.parent / 'superseded_submission.json').exists()]
    for prep in preps:
        if not (prep / 'submission.json').exists():
            continue
        startup = json.loads((prep / 'submission.json').read_text())
        jobs.append(startup['startup_job'].split(';')[0])
        p = prep / 'formal_submission.json'
        if p.exists():
            jobs.append(json.loads(p.read_text())['formal_job'].split(';')[0])
            formal_count += 1
        empty_record = prep / 'non_trial_empty_shards.json'
        if empty_record.exists():
            document = json.loads(empty_record.read_text())
            for item in document['jobs']:
                manifest = Path(item['run_manifest']['path'])
                import hashlib
                if hashlib.sha256(manifest.read_bytes()).hexdigest() != item['run_manifest']['sha256']:
                    raise RuntimeError('empty-shard run manifest changed')
                payload = json.loads(manifest.read_text())
                if payload['cases'][item['shard_index']::item['shards']]:
                    raise RuntimeError('cannot classify a shard with registered cases as a nontrial')
                empty_nontrials.add(item['job_id'])
    status = subprocess.run(['sacct', '-X', '-n', '-P', '-j', ','.join(jobs),
        '-o', 'JobID,State,ExitCode'], capture_output=True, text=True, check=True).stdout.strip()
    if status != previous:
        record = {'utc_epoch_s': time.time(), 'jobs': jobs, 'formal_count': formal_count,
                  'sacct': status, 'monitor_output': release.stdout.strip()}
        with LOG.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        print(json.dumps(record), flush=True)
        previous = status
    lines = [line.split('|') for line in status.splitlines() if line.strip()]
    physical_lines = [line for line in lines if line[0] not in empty_nontrials]
    failures = [line for line in physical_lines if line[1] in ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL')]
    if failures:
        signature = tuple(tuple(line) for line in failures)
        if signature not in reported_failures:
            print(json.dumps({'needs_repair': failures}), flush=True)
            reported_failures.add(signature)
    all_jobs_visible = all(any(line[0] == job or line[0].startswith(job + '_')
                              for line in lines) for job in jobs)
    if preps and formal_count == len(preps) and all_jobs_visible and physical_lines and all(line[1] == 'COMPLETED' and line[2] == '0:0' for line in physical_lines):
        print(json.dumps({'r16_r18_all_registered_physical_jobs_completed': True, 'jobs': jobs,
                          'preserved_failed_nontrial_empty_shards': sorted(empty_nontrials)}), flush=True)
        break
    # A real running/pending physical job is the dependency being awaited.
    time.sleep(30)
