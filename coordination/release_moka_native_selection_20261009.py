"""Release the registered selection after its same-launcher physical startup."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PREP = ROOT / 'results/harness_v5/moka_selection100_20261009_r3/preparation'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    if (PREP / 'formal_submission.json').exists():
        print('formal_already_submitted')
        return
    startup = json.loads((PREP / 'startup_submission.json').read_text())
    job = str(startup['job']).split(';')[0]
    state = subprocess.run(['sacct', '-n', '-X', '-j', job,
                            '--format=JobID,State,ExitCode', '-P'],
                           check=True, capture_output=True, text=True).stdout
    if '|COMPLETED|0:0' not in state:
        raise RuntimeError('physical startup has not completed: ' + state)
    contract = PREP.parent / 'physical/startup_preflight' / job / 'probe/contract.json'
    evidence = json.loads(contract.read_text())
    launcher = PREP / 'run_selection100.sbatch'
    manifest = PREP / 'selection100.json'
    plan = json.loads(manifest.read_text())
    snapshot_sha = hashlib.sha256(json.dumps(plan['source_snapshot'], sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
    if (evidence['status'] != 'pass' or evidence['requested_controls'] <= 0
            or evidence['manifest_sha256'] != ref(manifest)['sha256']
            or evidence['launcher_sha256'] != ref(launcher)['sha256']
            or evidence['source_snapshot_sha256'] != snapshot_sha
            or evidence['case'] not in plan['cases']):
        raise ValueError('same source/launcher/manifest/physical-case contract failed')
    env = {**startup['environment'], 'MOKA_TRANSFER_STARTUP_PREFLIGHT': '0',
           'MOKA_TRANSFER_STARTUP_CONTRACT': str(contract),
           'MOKA_TRANSFER_STARTUP_CONTRACT_SHA': ref(contract)['sha256'],
           'MOKA_TRANSFER_EXCLUDE_CASE_NAME': evidence['case_name']}
    check = subprocess.run(['bash', str(launcher)], capture_output=True, text=True,
                           env={**os.environ, **env, 'MOKA_TRANSFER_PREFLIGHT_ONLY': '1'})
    (PREP / 'formal_CPU_preflight.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    command = ['sbatch', '--parsable', '--array=0-7%8',
               '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
    with (PREP / 'formal_submission_intent.json').open('x') as stream:
        stream.write(json.dumps({'command': command, 'startup_contract': ref(contract),
                                 'startup_in_denominator': True, 'remaining_cases': 99}, indent=2) + '\n')
    job = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
    with (PREP / 'formal_submission.json').open('x') as stream:
        stream.write(json.dumps({'job': job, 'command': command, 'environment': env,
                                 'startup_contract': ref(contract), 'startup_in_denominator': True,
                                 'manifest': ref(manifest), 'launcher': ref(launcher),
                                 'remaining_cases': 99, 'confirmation': False}, indent=2) + '\n')
    print(json.dumps({'job': job, 'remaining_cases': 99, 'startup_in_denominator': True}))


if __name__ == '__main__':
    main()
