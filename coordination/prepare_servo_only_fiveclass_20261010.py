"""Pair the r14 selection states with their exact analytic controller + r16 tol."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
LOCK = ROOT / 'source_v5_grasp_truth_v3r9_20261010_r2'
OUT = ROOT / 'results/harness_v5/servo_only_fiveclass_selection_20261010_r1'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    attempts = ROOT / 'artifacts/contact_methods_intermediate_20261009_r14/attempts.jsonl'
    rows = [json.loads(line) for line in attempts.open() if line.strip()]
    sources = {}
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        selected = [r for r in rows if r['category'] == 'grasp_' + category
                    and r['method'].startswith('analytic')]
        if len(selected) != 100 or len({r['state_sha256'] for r in selected}) != 100:
            raise ValueError('exact 100 unique r14 selection states required: ' + category)
        old = next(p / 'preparation/selection.json' for p in Path(selected[0]['output_dir']).parents
                   if (p / 'preparation/selection.json').exists())
        plan = copy.deepcopy(json.loads(old.read_text()))
        indexed = {c['name']: c for c in plan['cases']}
        if any(indexed[r['case']]['state_sha256'] != r['state_sha256'] for r in selected):
            raise ValueError('r14 state mismatch')
        parent = Path(plan['source_path'])
        if parent not in sources:
            source = ROOT / ('source_v5_servo_only_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
            shutil.copytree(parent, source, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            runtime = source / 'robots/libero/v5_runtime.py'
            body = runtime.read_text()
            old_line = '        move_options = {}\n'
            if body.count(old_line) != 1:
                raise ValueError('unexpected baseline servo: ' + str(parent))
            runtime.write_text(body.replace(old_line,
                '        move_options = {"tol": min(.012, tolerance_m)}\n'))
            # Private scorer changes do not change public control or stop rules.
            private = ('robots/libero/v5_grasp_truth.py', 'robots/libero/v5_grasp_support_worker.py')
            for relative in private:
                shutil.copyfile(LOCK / relative, source / relative)
            parent_identity = plan['source_snapshot']
            paths = list(dict.fromkeys([r['relative_path'] for r in parent_identity['files']]
                                      + list(private) + ['robots/libero/v5_runtime.py']))
            identity = {**parent_identity, 'path': str(source), 'snapshot_id': source.name,
                'commit': source.name, 'git_base_commit': parent_identity['commit'],
                'parent_snapshot': pin(parent / 'source_snapshot.json'),
                'purpose': 'r14 controller unchanged except move_to tol=min(.012,tolerance_m)',
                'private_truth_registration': 'grasp_truth_v3_1153_20261009',
                'files': [{**pin(source / p), 'relative_path': p} for p in paths]}
            (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
            archive = source.with_suffix('.tar')
            with tarfile.open(archive, 'x') as stream:
                for child in source.iterdir():
                    stream.add(child, arcname=child.name)
            identity['archive'] = {**pin(archive), 'archive_complete': True}
            sources[parent] = (source, identity)
        source, identity = sources[parent]
        prep = OUT / (category + '_analytic') / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        plan.update(source_path=str(source), source_commit=source.name, source_snapshot=identity,
            adapter_path=str(ADAPTER), producer=pin(producer), parent_plan=pin(old),
            producer_dependencies=[pin(producer), *[pin(ADAPTER / 'scripts' / name) for name in (
                'probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
                'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
            references=[*plan['references'], pin(old), pin(attempts)],
            purpose='same r14 selection pool; only public control change is r16 servo tolerance',
            qualification_authorized=False, training_allowed=False, confirmation=False,
            new_training_rows=0, baseline_method=selected[0]['method'])
        plan['cases'] = [indexed[r['case']] for r in selected]
        for case in plan['cases']:
            case['paired_baseline_case'] = case['name']
            case['name'] += '_servo_only'
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=str(ADAPTER),
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--nice=0',
            '--export=ALL', str(LAUNCH)], env=env, capture_output=True, text=True, check=True)
        receipt = {'name': prep.parent.name, 'startup_job': submitted.stdout.strip(),
            'plan': pin(path), 'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout,
            'qualification_allowed': False, 'private_truth_rule_unchanged': True,
            'public_control_change': 'move_to tol=min(.012,tolerance_m)', 'paired_baseline': pin(old)}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
