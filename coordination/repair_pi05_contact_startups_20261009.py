"""Replace zero-control starts whose producer path was overwritten by r2."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r1'
OUTPUT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r3'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    for category in ('bowl', 'bottle', 'box', 'cup', 'frypan'):
        cell = f'grasp_{category}_pi05'
        previous = OLD / cell / 'preparation/startup_submission.json'
        startup = json.loads(previous.read_text())
        previous_plan = Path(startup['manifest']['path'])
        if ref(previous_plan) != startup['manifest']:
            raise ValueError('old plan changed')
        job = str(startup['job']).split(';')[0]
        state = subprocess.run(['sacct', '-n', '-X', '-j', job,
            '--format=JobID,State,ExitCode', '-P'], capture_output=True, text=True, check=True).stdout
        log = ROOT / f'results/slurm-{job}_0.log'
        if '|FAILED|1:0' not in state or 'registered producer changed:' not in log.read_text():
            raise ValueError('not the expected producer-hash startup fault')
        if any((OLD / cell / f'job{job}').rglob('episodes.jsonl')):
            raise ValueError('unexpected physical ledger: inspect before repair')
        prep = OUTPUT / cell / 'preparation'
        if (prep / 'startup_submission.json').exists():
            continue
        prep.mkdir(parents=True, exist_ok=False)
        # Keep an immutable producer copy beside each plan. Never register
        # the mutable working prepare_contact_methods_selection path again.
        producer = prep / 'producer.py'
        producer.write_bytes(Path(__file__).read_bytes())
        plan = json.loads(previous_plan.read_text())
        old_producer = plan['producer']['path']
        plan.update(producer=ref(producer), producer_dependencies=[ref(producer),
            *[r for r in plan['producer_dependencies'] if r['path'] != old_producer]],
            references=[*plan['references'], ref(previous_plan), ref(log)],
            supersedes_startup={'job': job, 'physical_controls': 0,
                'reason': 'producer working path overwritten after r1 plan registration; prior failure retained'},
            unchanged_contact_method=True)
        manifest = prep / 'selection.json'
        manifest.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(startup['environment'])
        env.update(PERTURB_SKILL_PLAN=str(manifest), PERTURB_SKILL_PLAN_SHA=ref(manifest)['sha256'],
                   PERTURB_SKILL_OUTPUT=str(OUTPUT / cell))
        launcher = Path(startup['launcher']['path'])
        if ref(launcher) != startup['launcher']:
            raise ValueError('launcher changed')
        cpu = subprocess.run(['bash', str(launcher)], env={**os.environ, **env,
            'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        result = subprocess.run(['sbatch', '--parsable', '--array=0', '--nice=0',
            '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)],
            text=True, capture_output=True, check=True)
        record = {'job': result.stdout.strip(), 'environment': env, 'manifest': ref(manifest),
            'launcher': ref(launcher), 'source_unchanged': plan['source_snapshot'],
            'superseded_job': job, 'physical_startup': 'pending', 'confirmation': False}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'cell': cell, 'job': record['job'], 'prior_job': job,
                          'CPU_preflight': 'pass'}), flush=True)


if __name__ == '__main__':
    main()
