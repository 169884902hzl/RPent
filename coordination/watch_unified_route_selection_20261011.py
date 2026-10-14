"""Release only paired plans that have passed their exact physical startup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
RUN = Path(os.environ.get('UNIFIED_ROUTE_RUN', str(ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r2')))
LAUNCH = ROOT/'coordination/run_v5_grasp_measurement_development_20261011.sbatch'
MEASURED = ROOT/'coordination/grasp_measurement_development_closed_20261011_r1/manifest.json'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def available_slots():
    node = subprocess.check_output(['scontrol', 'show', 'node', 'node01', '-o'], text=True)
    allocated = next((s.split('=', 1)[1] for s in node.split() if s.startswith('AllocTRES=')), '')
    gpu = next((int(s.rsplit('=', 1)[1]) for s in allocated.split(',') if s.startswith('gres/gpu=')), 0)
    return max(1, 4-gpu)


def main():
    items = json.loads((RUN/'startup_manifest.json').read_text())
    categories = set(filter(None, os.environ.get('UNIFIED_ROUTE_CATEGORIES', '').split(',')))
    if categories:
        items = [item for item in items if item['category'] in categories]
    if not items:
        raise ValueError('no registered startups selected for monitoring')
    last = None
    while True:
        jobs = [item['startup_job'] for item in items]
        for item in items:
            record = Path(item['plan']['path']).parent/'formal_measurement_submission.json'
            if record.exists():
                jobs.append(json.loads(record.read_text())['formal_job'])
        result = subprocess.check_output(['sacct', '-X', '-n', '-j', ','.join(jobs),
                                         '--format=JobID,State,ExitCode', '-P'], text=True)
        states = {}
        for line in result.splitlines():
            fields = line.split('|')
            if len(fields) >= 3:
                states[fields[0]] = (fields[1].split()[0], fields[2])
        if states != last:
            print(json.dumps({'observed_jobs': states, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}), flush=True)
            last = states
        failures = [(job, state) for job, state in states.items() if state[0] in
                    {'FAILED', 'TIMEOUT', 'CANCELLED', 'NODE_FAIL', 'OUT_OF_MEMORY', 'PREEMPTED'}]
        if failures:
            for job, state in failures:
                base, _, part = job.partition('_')
                log = ROOT/'results'/f'slurm-{base}_{part or "4294967294"}.log'
                record = {'job': job, 'state': state, 'log': str(log),
                          'tail': log.read_text(errors='replace')[-6000:] if log.exists() else None}
                (RUN/f'monitor_failure_{job}.json').write_text(json.dumps(record, indent=2)+'\n')
                print(json.dumps(record), flush=True)
            raise SystemExit(1)
        all_done = True
        slots = available_slots()
        for item in items:
            plan_path = Path(item['plan']['path'])
            output = plan_path.parent.parent
            record = plan_path.parent/'formal_measurement_submission.json'
            if not record.exists():
                all_done = False
                startup = item['startup_job']
                if states.get(startup) != ('COMPLETED', '0:0'):
                    continue
                if not MEASURED.exists():
                    continue
                measured = json.loads(MEASURED.read_text())
                if (measured['registered_states'] != 119 or measured['complete_control_trace'] != 119
                        or measured['whole_skill_trace_not_saved'] != 0
                        or measured['old_pan16']['n'] != 16
                        or measured['old_pan16']['new_truth_unknown'] != 0):
                    raise ValueError('full measurement replay remains unresolved')
                contract = output/f'job{startup}/part0/startup_contract.json'
                checked = json.loads(contract.read_text())
                if (checked['status'] != 'pass' or checked['physical_controls'] <= 0
                        or checked['plan_sha256'] != item['plan']['sha256']
                        or checked['launcher_sha256'] != pin(LAUNCH)['sha256']):
                    raise ValueError('physical startup differs from registered plan/launcher')
                plan = json.loads(plan_path.read_text())
                env = dict(os.environ, PERTURB_SKILL_PLAN=str(plan_path),
                    PERTURB_SKILL_PLAN_SHA=item['plan']['sha256'],
                    PERTURB_SKILL_SOURCE=plan['source_path'], PERTURB_SKILL_ADAPTER=plan['adapter_path'],
                    PERTURB_SKILL_OUTPUT=str(output), PERTURB_SKILL_STARTUP='0',
                    PERTURB_SKILL_STARTUP_CONTRACT=str(contract), PERTURB_SKILL_SHARDS='8')
                job = subprocess.check_output(['sbatch', '--parsable', '--exclude=node02', '--nice=500',
                    '--time=01:00:00', '--array', f'0-7%{slots}', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                    env=env, text=True).strip()
                data = {'formal_job': job, 'startup_job': startup, 'startup_contract': pin(contract),
                        'plan': item['plan'], 'launcher': pin(LAUNCH), 'shards': 8, 'remaining_cases': 99,
                        'actual_startup_controls': checked['physical_controls'],
                        'resource_rules': {'exclude': 'node02', 'nice': 500}, 'confirmation': False}
                record.write_text(json.dumps(data, indent=2)+'\n')
                print(json.dumps(data), flush=True)
            else:
                formal = json.loads(record.read_text())
                parts = [states.get(f'{formal["formal_job"]}_{i}') for i in range(8)]
                finished = all(state == ('COMPLETED', '0:0') for state in parts)
                all_done &= finished
                if not finished:
                    active = next((i for i, state in enumerate(parts)
                                   if state != ('COMPLETED', '0:0')), 0)
                    current = subprocess.check_output(['scontrol', 'show', 'job',
                        f'{formal["formal_job"]}_{active}', '-o'], text=True)
                    throttle = next((int(field.split('=', 1)[1]) for field in current.split()
                                     if field.startswith('ArrayTaskThrottle=')), None)
                    if throttle != slots:
                        update = subprocess.run(['scontrol', 'update', f'JobId={formal["formal_job"]}',
                            f'ArrayTaskThrottle={slots}'], capture_output=True, text=True)
                        if update.returncode:
                            # Slurm rejects a parent update after its first
                            # materialised element finishes. Other category
                            # arrays remain independently schedulable.
                            if 'Job has already finished' not in update.stderr:
                                raise RuntimeError(update.stderr)
                            print(json.dumps({'throttle_parent_finished':formal['formal_job'],
                                              'requested':slots,'current':throttle}), flush=True)
        if all_done:
            return
        # These are real submitted dependencies; the primary agent continues CPU work.
        time.sleep(60)


if __name__ == '__main__':
    main()
