"""Same-state coherent contact patches, pad depths and public wrist orientation cost."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r3'
NEW = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r5'
STAGING = ROOT / 'coordination/geometric_grasp_contactpatch_staging_20261010_r1'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    sources = {}
    for category, group, sampling in [(category, category + '_coherent_sampling', True)
            for category in ('bottle', 'bowl', 'box', 'cup', 'frypan')]:
        prior = OLD / (category + '_geometric_sampling') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(prior.read_text()))
        parent = Path(plan['source_path'])
        if parent not in sources:
            source = ROOT / ('source_v5_geometric_grasp_20261010_r7_' + parent.name.rsplit('_', 1)[-1])
            shutil.copytree(parent, source, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            changed = ['robots/libero/v5_geometric_grasp.py',
                       'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']
            for relative in changed:
                shutil.copyfile(STAGING / relative, source / relative)
            analytic = source / 'robots/libero/v5_analytic_grasp.py'
            body = analytic.read_text()
            before = 'executor.p._last_obs_eef_pos, yaw, geometry)'
            if body.count(before) != 1:
                raise ValueError('must add public quaternion to exactly the sampler call')
            body = body.replace(before, 'executor.p._last_obs_eef_pos, yaw, geometry,\n'
                "                current_body_quat_xyzw=observation['robot0_eef_quat'])")
            compile(body, str(analytic), 'exec')
            analytic.write_text(body)
            changed.append('robots/libero/v5_analytic_grasp.py')
            tests = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', *[
                'tests/unit_tests/robots/libero/' + name for name in (
                    'test_v5_geometric_grasp.py', 'test_v5_grasp_geometry.py',
                    'test_v5_analytic_grasp.py::test_unmeasured_handle_gets_close_wrist_view_before_contact_is_rejected',
                    'test_v5_analytic_grasp.py::test_precontact_tracking_uses_prior_identity_not_category_only_refresh',
                    'test_v5_analytic_grasp.py::test_failed_approach_never_calls_policy_or_closes')]]
            checked = subprocess.run(tests, cwd=source, env=dict(os.environ, PYTHONPATH=str(source)),
                                     text=True, capture_output=True)
            (source / 'CPU_local_opposition.log').write_text(checked.stdout + checked.stderr)
            checked.check_returncode()
            paths = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']] + changed))
            identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
                        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
                        'purpose': 'coherent opposing contact patches; collision-checked contact depths and jaw flips; measured wrist cost',
                        'CPU_validation': {'command': tests, 'output': checked.stdout},
                        'files': [{**pin(source / relative), 'relative_path': relative} for relative in paths]}
            (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
            archive = source.with_suffix('.tar')
            with tarfile.open(archive, 'x') as stream:
                for child in source.iterdir():
                    stream.add(child, arcname=child.name)
            identity['archive'] = {**pin(archive), 'archive_complete': True}
            sources[parent] = source, identity
        source, identity = sources[parent]
        prep = NEW / group / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        condition = next(iter(plan['conditions'].values()))
        condition['overrides'].update(analytic_identity_guard_v1=True, analytic_geometry_v1=True,
            grasp_geometry_cleanup_v1=True, geometric_grasp_sampling_v1=sampling)
        plan.update(source_path=str(source), source_snapshot=identity, source_commit=source.name,
                    parent_plan=pin(prior), producer=pin(producer),
                    producer_dependencies=[pin(producer), *[d for d in plan['producer_dependencies']
                        if d['path'] != plan['producer']['path']]],
                    purpose=identity['purpose'], private_truth_rule_unchanged=True)
        plan['conditions'] = {group: condition}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case'] + '_' + group
            case['condition'] = group
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
                   PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
                   PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, text=True, capture_output=True)
        (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
        checked.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                                   env=env, text=True, capture_output=True, check=True)
        receipt = {'name': group, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
                   'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout,
                   'qualification_allowed': False, 'training_allowed': False,
                   'private_truth_rule_unchanged': True, 'public_method': group}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
