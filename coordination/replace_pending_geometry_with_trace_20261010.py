"""Replace untouched pending startups with trace-preserving plans, keeping all records."""
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r1'
NEW = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r2'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9_trace_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


with (ROOT / 'coordination/registered_grasp_v3r9_release.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    for prep in sorted(OLD.glob('*/preparation')):
        receipt = json.loads((prep / 'submission.json').read_text())
        job = receipt['startup_job'].split(';')[0]
        state = subprocess.check_output(['squeue', '-h', '-j', job, '-o', '%T'], text=True).strip()
        if state != 'PENDING' or (prep / 'formal_submission.json').exists():
            raise RuntimeError(f'Only untouched pending startup may be replaced: {job} {state}')
        plan = copy.deepcopy(json.loads((prep / 'selection.json').read_text()))
        out = NEW / prep.parent.name / 'preparation'
        out.mkdir(parents=True, exist_ok=False)
        producer = out / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        dependencies = []
        for dep in plan['producer_dependencies']:
            path = Path(dep['path'])
            if path == Path(plan['producer']['path']):
                continue
            if '/perturb_contact_methods_adapter_20261010_v3r9/' in str(path):
                path = ADAPTER / path.relative_to(ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9')
            dependencies.append(pin(path))
        plan.update(adapter_path=str(ADAPTER), producer=pin(producer),
                    producer_dependencies=[pin(producer), *dependencies],
                    diagnostic_trace_patch=pin(ADAPTER / 'source_identity.json'),
                    replaced_pending_plan=pin(prep / 'selection.json'),
                    physical_control_source_unchanged=True)
        path = out / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
                   PERTURB_SKILL_SOURCE=plan['source_path'], PERTURB_SKILL_ADAPTER=str(ADAPTER),
                   PERTURB_SKILL_OUTPUT=str(out.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        check = subprocess.run(['bash', receipt['launcher']['path']], cwd='/tmp', env=env,
                               capture_output=True, text=True)
        (out / 'CPU_preflight.log').write_text(check.stdout + check.stderr)
        check.check_returncode()
        # Recheck under the release lock before cancellation, after CPU work.
        state = subprocess.check_output(['squeue', '-h', '-j', job, '-o', '%T'], text=True).strip()
        if state != 'PENDING':
            raise RuntimeError(f'Startup began while preparing replacement: {job} {state}')
        superseded = {'old_startup': job, 'old_submission': pin(prep / 'submission.json'),
                      'reason': 'save complete contact trace before launching new geometry comparisons',
                      'old_job_never_started': True, 'new_preparation': str(out),
                      'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (prep / 'superseded_submission.json').write_text(json.dumps(superseded, indent=2) + '\n')
        subprocess.run(['scancel', job], check=True)
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL',
                                    receipt['launcher']['path']], env=env, capture_output=True, text=True, check=True)
        receipt.update(startup_job=submitted.stdout.strip(), plan=pin(path),
                       CPU_preflight=check.stdout, superseded_submission=superseded,
                       adapter_trace_identity=pin(ADAPTER / 'source_identity.json'))
        (out / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'name': out.parent.name, 'old_job': job, 'new_startup': receipt['startup_job']}), flush=True)
