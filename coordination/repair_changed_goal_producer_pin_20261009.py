"""Retry the two zero-control producer faults, preserving method and states."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'results/harness_v5/perturb_changed_goal_selection_20261009_r3'
OUTPUT = ROOT / 'results/harness_v5/perturb_changed_goal_selection_20261009_r4'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    for cell in ('place_on', 'place_in'):
        registration = OLD / cell / 'preparation/startup_submission.json'
        old = json.loads(registration.read_text())
        manifest_old = Path(old['manifest']['path'])
        launcher = Path(old['launcher']['path'])
        if ref(manifest_old) != old['manifest'] or ref(launcher) != old['launcher']:
            raise ValueError('old registered source changed')
        job = str(old['job']).split(';')[0]
        state = subprocess.check_output(['sacct', '-n', '-X', '-j', job,
            '--format=JobID,State,ExitCode', '-P'], text=True)
        log = ROOT / f'results/slurm-{job}_0.log'
        if '|FAILED|1:0' not in state or 'registered producer changed:' not in log.read_text():
            raise ValueError('not a zero-control producer startup failure')
        if any((OLD / cell / f'job{job}').rglob('episodes.jsonl')):
            raise ValueError('physical ledger needs inspection before retry')
        prep = OUTPUT / cell / 'preparation'
        if (prep / 'startup_submission.json').exists():
            continue
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        producer.write_bytes(Path(__file__).read_bytes())
        plan = json.loads(manifest_old.read_text())
        previous_producer = plan['producer']['path']
        plan.update(producer=ref(producer), producer_dependencies=[ref(producer),
            *[r for r in plan['producer_dependencies'] if r['path'] != previous_producer]],
            references=[*plan['references'], ref(manifest_old), ref(log)],
            supersedes_startup={'job': job, 'physical_controls': 0,
                'reason': 'mutable producer overwritten; fixed copy pinned beside new plan'},
            unchanged_control_method=True)
        manifest = prep / 'selection.json'
        manifest.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(old['environment'])
        env.update(PERTURB_SKILL_PLAN=str(manifest), PERTURB_SKILL_PLAN_SHA=ref(manifest)['sha256'],
                   PERTURB_SKILL_OUTPUT=str(OUTPUT / cell))
        cpu = subprocess.run(['bash', str(launcher)], cwd='/tmp', env={**os.environ, **env,
            'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        command = ['sbatch', '--parsable', '--array=0', '--nice=0',
            '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
        result = subprocess.run(command, cwd='/tmp', text=True, capture_output=True, check=True)
        record = {'job': result.stdout.strip(), 'command': command, 'environment': env,
            'manifest': ref(manifest), 'launcher': ref(launcher), 'prior_zero_control_job': job,
            'physical_startup': 'pending', 'confirmation': False}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'cell': cell, 'job': record['job'], 'prior_job': job}), flush=True)


if __name__ == '__main__':
    main()
