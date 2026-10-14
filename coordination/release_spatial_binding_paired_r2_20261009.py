"""Preserve the startup episode and release the other nine paired episodes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PREP = ROOT / 'results/harness_v5/spatial_transfer_binding_A3_paired10_20261009_r2/preparation/A3-N'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    if (PREP / 'formal_submission.json').exists():
        print((PREP / 'formal_submission.json').read_text())
        return
    startup = json.loads((PREP / 'startup_submission.json').read_text())
    index_path = PREP / 'manifest.json'
    if ref(index_path) != startup['manifest']:
        raise ValueError('manifest changed after startup')
    index = json.loads(index_path.read_text())
    env = dict(startup['environment'])
    job = str(startup['job']).split(';')[0]
    output = Path(env['INTERIM574_OUTPUT_ROOT']) / f'A3-N/startup_preflight/job{job}/part0'
    contract_path = output / 'startup_contract.json'
    state = subprocess.run(['sacct', '-n', '-X', '-j', job,
        '--format=JobID,State,ExitCode', '-P'], capture_output=True, text=True, check=True).stdout
    if not contract_path.exists() or '|COMPLETED|0:0' not in state:
        print(json.dumps({'status': 'waiting_physical_startup', 'job': job, 'sacct': state.strip()}))
        return
    launcher = Path(startup['launcher'])
    contract = json.loads(contract_path.read_text())
    expected = {'cohort': 'A3-N', 'source_path': index['source_path'],
        'source_commit': index['source_commit'], 'manifest_index_sha256': ref(index_path)['sha256'],
        'launcher_sha256': ref(launcher)['sha256']}
    if contract.get('status') != 'pass' or not contract.get('physical_actions'):
        raise ValueError('startup did not actually execute a physical action')
    if any(contract.get(k) != v for k, v in expected.items()):
        raise ValueError('startup source/launcher/index identity mismatch')
    env.update(INTERIM574_STARTUP_PREFLIGHT='0', INTERIM574_STARTUP_CONTRACT=str(contract_path))
    cpu = subprocess.run(['bash', str(launcher)], cwd='/tmp', env={**os.environ, **env,
        'INTERIM574_PREFLIGHT_ONLY': '1'}, capture_output=True, text=True)
    (PREP / 'formal_cpu_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    command = ['sbatch', '--parsable', '--array=1-9%8', '--nice=0',
        '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
    result = subprocess.run(command, cwd='/tmp', capture_output=True, text=True, check=True)
    record = {'job': result.stdout.strip(), 'command': command, 'environment': env,
        'startup_contract': ref(contract_path), 'manifest': ref(index_path), 'launcher': ref(launcher),
        'startup_episode_preserved': contract['episode'], 'remaining_episodes': 9,
        'confirmation': False, 'training_allowed': False}
    (PREP / 'formal_submission.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
