"""Finish public horizontal-finger sampling before untouched selection startups run."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r2'
NEW = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r3'
STAGING = ROOT / 'coordination/geometric_grasp_staging_20261010_r3'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def snapshot(parent, identity):
    source = ROOT / ('source_v5_geometric_grasp_20261010_r5_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    changed = ['robots/libero/v5_analytic_grasp.py', 'robots/libero/v5_geometric_grasp.py',
               'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
               'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']
    for relative in changed:
        shutil.copyfile(STAGING / relative, source / relative)
    # These snapshots intentionally retain r14's public verifier/controller.
    # Tests of the later r18 verifier are checked in its own source, and must
    # not force unrelated verifier or route behavior into this geometry pair.
    tests = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', *[
        'tests/unit_tests/robots/libero/' + name for name in ('test_v5_geometric_grasp.py',
        'test_v5_grasp_geometry.py',
        'test_v5_analytic_grasp.py::test_unmeasured_handle_gets_close_wrist_view_before_contact_is_rejected',
        'test_v5_analytic_grasp.py::test_precontact_tracking_uses_prior_identity_not_category_only_refresh',
        'test_v5_analytic_grasp.py::test_failed_approach_never_calls_policy_or_closes')]]
    result = subprocess.run(tests, cwd=source, env=dict(os.environ, PYTHONPATH=str(source)),
                            capture_output=True, text=True)
    (source / 'CPU_geometry_sideposes.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    paths = list(dict.fromkeys([r['relative_path'] for r in identity['files']] + changed))
    result_identity = {**identity, 'path': str(source), 'snapshot_id': source.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'actual horizontal fingers with public quaternion feedback; wrist refinement before contact sampling',
        'CPU_validation': {'command': tests, 'output': result.stdout},
        'files': [{**pin(source / relative), 'relative_path': relative} for relative in paths]}
    (source / 'source_identity_v3r9.json').write_text(json.dumps(result_identity, indent=2) + '\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():
            stream.add(child, arcname=child.name)
    result_identity['archive'] = {**pin(archive), 'archive_complete': True}
    return source, result_identity


with (ROOT / 'coordination/registered_grasp_v3r9_release.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    sources = {}
    for prep in sorted(OLD.glob('*/preparation')):
        if not (prep.parent.name.endswith('geometric_sampling') or prep.parent.name == 'frypan_connected_handle'):
            continue
        receipt = json.loads((prep / 'submission.json').read_text()); job = receipt['startup_job'].split(';')[0]
        state = subprocess.check_output(['squeue', '-h', '-j', job, '-o', '%T'], text=True).strip()
        if state != 'PENDING' or (prep / 'formal_submission.json').exists():
            raise RuntimeError(f'Only untouched pending startup may be replaced: {job} {state}')
        plan = copy.deepcopy(json.loads((prep / 'selection.json').read_text()))
        parent = Path(plan['source_path'])
        if parent not in sources:
            sources[parent] = snapshot(parent, plan['source_snapshot'])
        source, identity = sources[parent]
        out = NEW / prep.parent.name / 'preparation'; out.mkdir(parents=True, exist_ok=False)
        producer = out / 'producer.py'; shutil.copyfile(Path(__file__), producer)
        plan.update(source_path=str(source), source_snapshot=identity,
                    producer_dependencies=[pin(producer), *[d for d in plan['producer_dependencies']
                        if d['path'] != plan['producer']['path']]],
                    producer=pin(producer), replaced_pending_plan=pin(prep / 'selection.json'),
                    purpose=identity['purpose'], private_truth_rule_unchanged=True,
                    physical_control_source_unchanged=False)
        path = out / 'selection.json'; path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
            PERTURB_SKILL_OUTPUT=str(out.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        check = subprocess.run(['bash', receipt['launcher']['path']], cwd='/tmp', env=env,
                               capture_output=True, text=True)
        (out / 'CPU_preflight.log').write_text(check.stdout + check.stderr); check.check_returncode()
        state = subprocess.check_output(['squeue', '-h', '-j', job, '-o', '%T'], text=True).strip()
        if state != 'PENDING':
            raise RuntimeError(f'Startup began while preparing replacement: {job} {state}')
        superseded = {'old_startup': job, 'old_submission': pin(prep / 'submission.json'),
                      'reason': identity['purpose'], 'old_job_never_started': True,
                      'new_preparation': str(out)}
        (prep / 'superseded_submission.json').write_text(json.dumps(superseded, indent=2) + '\n')
        subprocess.run(['scancel', job], check=True)
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL',
                                    receipt['launcher']['path']], env=env, capture_output=True, text=True, check=True)
        receipt.update(startup_job=submitted.stdout.strip(), plan=pin(path),
                       CPU_preflight=check.stdout, superseded_submission=superseded,
                       public_method_version='public-geometric-grasp/2-dev')
        (out / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'name': out.parent.name, 'old_job': job, 'new_startup': receipt['startup_job']}), flush=True)
