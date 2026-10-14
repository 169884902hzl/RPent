"""Queue physical development startups while the full measurement replay runs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
RUN = Path(os.environ.get('UNIFIED_ROUTE_RUN', str(ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r2')))
MEASURED = ROOT/'coordination/grasp_measurement_development_closed_20261011_r1/manifest.json'
MEASUREMENT_RUN = ROOT/'results/harness_v5/grasp_measurement_development_20261011_r4'
LAUNCH = ROOT/'coordination/run_v5_grasp_measurement_development_20261011.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    measurement_startups = []
    for registered in json.loads((MEASUREMENT_RUN/'startup_manifest.json').read_text()):
        output = Path(registered['plan']['path']).parent.parent
        contract = output/f'job{registered["startup_job"]}/part0/startup_contract.json'
        checked = json.loads(contract.read_text())
        row = json.loads(Path(checked['episodes']['path']).read_text().splitlines()[0])
        phase = row.get('private_grasp_phase') or {}
        if (checked['status'] != 'pass' or checked['physical_controls'] <= 0
                or phase.get('trace_version') != 'every-executed-skill-control/1-dev'
                or not phase.get('samples')):
            raise ValueError('measurement startup has no full physical trace')
        measurement_startups.append(pin(contract))
    if len(measurement_startups) != 5:
        raise ValueError('five measurement startups required')
    items = json.loads((RUN/'manifest.json').read_text())['registered_plans']
    receipt = RUN/'startup_manifest.json'
    registrations = json.loads(receipt.read_text()) if receipt.exists() else []
    submitted = {entry['plan']['path'] for entry in registrations}
    categories = set(filter(None, os.environ.get('UNIFIED_ROUTE_CATEGORIES', '').split(',')))
    for item in sorted(items, key=lambda entry: (entry['arm'] != 'unified', entry['category'])):
        if categories and item['category'] not in categories:
            continue
        if item['plan']['path'] in submitted:
            continue
        plan_path = Path(item['plan']['path'])
        if pin(plan_path) != item['plan']:
            raise ValueError('paired development plan changed')
        plan = json.loads(plan_path.read_text())
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(plan_path),
                   PERTURB_SKILL_PLAN_SHA=item['plan']['sha256'],
                   PERTURB_SKILL_SOURCE=plan['source_path'],
                   PERTURB_SKILL_ADAPTER=plan['adapter_path'],
                   PERTURB_SKILL_OUTPUT=str(plan_path.parent.parent),
                   PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        check = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env,
                               capture_output=True, text=True)
        (plan_path.parent/'submission_CPU_preflight.log').write_text(check.stdout+check.stderr)
        check.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        job = subprocess.check_output(['sbatch', '--parsable', '--exclude=node02', '--nice=500',
            '--time=00:30:00', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
            env=env, text=True).strip()
        registrations.append({**item, 'physical_submitted': True, 'CPU_preflight': 'pass',
                              'CPU_preflight_log': pin(plan_path.parent/'submission_CPU_preflight.log'),
                              'startup_job': job, 'launcher': pin(LAUNCH),
                              'measurement_startups': measurement_startups,
                              'full_measurement_report_pending': not MEASURED.exists(), 'confirmation': False})
        receipt.write_text(json.dumps(registrations, indent=2)+'\n')
        print(json.dumps(registrations[-1]), flush=True)


if __name__ == '__main__':
    main()
