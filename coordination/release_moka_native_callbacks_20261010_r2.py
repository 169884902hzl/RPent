"""Release repaired development selection after the exact regression startup."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PREP = ROOT / 'results/harness_v5/moka_native_callbacks_selection100_20261010_r2/preparation'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    formal = PREP / 'formal_submission.json'
    if formal.exists():
        print(formal.read_text())
        return
    startup = json.loads((PREP / 'startup_regression_submission.json').read_text())
    job = str(startup['job']).split(';')[0]
    status = subprocess.run(['sacct', '-n', '-X', '-j', job, '-P',
                             '-o', 'JobID,State,ExitCode'],
                            check=True, capture_output=True, text=True).stdout
    if '|COMPLETED|0:0' not in status:
        raise RuntimeError('regression startup incomplete: ' + status)
    contract = PREP.parent / 'physical/startup_preflight' / job / 'probe/contract.json'
    evidence = json.loads(contract.read_text())
    manifest, launcher = PREP / 'selection100.json', PREP / 'run_selection100.sbatch'
    plan = json.loads(manifest.read_text())
    source_sha = hashlib.sha256(json.dumps(plan['source_snapshot'], sort_keys=True,
                                           separators=(',', ':')).encode()).hexdigest()
    if (evidence['status'] != 'pass' or evidence['requested_controls'] <= 0
            or evidence['manifest_sha256'] != pin(manifest)['sha256']
            or evidence['launcher_sha256'] != pin(launcher)['sha256']
            or evidence['source_snapshot_sha256'] != source_sha
            or evidence['case'] not in plan['cases']
            or plan['qualification_authorized'] or plan['training_allowed']):
        raise ValueError('same-source physical startup contract failed')
    rows = [json.loads(line) for line in (contract.parent / 'episodes.jsonl').read_text().splitlines()
            if line.strip()]
    if (len(rows) != 1 or rows[0].get('case_had_infrastructure_failure')
            or rows[0].get('result', {}).get('infrastructure_failure')
            or rows[0].get('first_receipt', {}).get('verification') == 'execution_error'):
        raise ValueError('regression startup retains an execution/infrastructure failure')
    env = {**startup['environment'], 'MOKA_TRANSFER_STARTUP_PREFLIGHT': '0',
           'MOKA_TRANSFER_STARTUP_CONTRACT': str(contract),
           'MOKA_TRANSFER_STARTUP_CONTRACT_SHA': pin(contract)['sha256'],
           'MOKA_TRANSFER_EXCLUDE_CASE_NAME': evidence['case_name']}
    check = subprocess.run(['bash', str(launcher)], capture_output=True, text=True,
                           env={**os.environ, **env, 'MOKA_TRANSFER_PREFLIGHT_ONLY': '1'})
    (PREP / 'formal_CPU_preflight.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    command = ['sbatch', '--parsable', '--array=0-7%8', '--export=ALL', str(launcher)]
    receipt = {'command': command, 'environment': env, 'startup_contract': pin(contract),
               'startup_job': job, 'startup_in_denominator': True, 'remaining_cases': 99,
               'manifest': pin(manifest), 'launcher': pin(launcher), 'producer': pin(Path(__file__)),
               'confirmation': False, 'training_allowed': False,
               'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (PREP / 'formal_submission_intent.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    submitted = subprocess.run(command, env={**os.environ, **env},
                               capture_output=True, text=True, check=True)
    receipt['job'] = submitted.stdout.strip().split(';')[0]
    with formal.open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
