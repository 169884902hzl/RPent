"""Keep the exact r14 pi0.5 controller; add only the locked private scorer."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASELINE = ROOT / 'artifacts/contact_methods_intermediate_20261009_r14/attempts.jsonl'
LOCK = ROOT / 'source_v5_grasp_truth_v3r9_20261010_r2'
SOURCE = ROOT / 'source_v5_r14_pi05_locked_v3_20261010_r1'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    rows = list(map(json.loads, BASELINE.open()))
    snapshot = None
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        selected = [r for r in rows if r['category'] == 'grasp_' + category and r['method'] == 'pi05']
        if len(selected) != 100 or len({r['state_sha256'] for r in selected}) != 100:
            raise ValueError('exact original r14 pi05 selection100 required')
        parent_plan = next(p / 'preparation/selection.json' for p in Path(selected[0]['output_dir']).parents
                           if (p / 'preparation/selection.json').is_file())
        plan = copy.deepcopy(json.loads(parent_plan.read_text()))
        parent = Path(plan['source_path'])
        if snapshot is None:
            shutil.copytree(parent, SOURCE, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            private = ('robots/libero/v5_grasp_truth.py', 'robots/libero/v5_grasp_support_worker.py')
            for relative in private:
                shutil.copyfile(LOCK / relative, SOURCE / relative)
            paths = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']] + list(private)))
            # The control and public verification implementation are byte-identical.
            for relative in paths:
                if relative not in private and pin(parent / relative)['sha256'] != pin(SOURCE / relative)['sha256']:
                    raise ValueError('pi05 control changed')
            snapshot = {**plan['source_snapshot'], 'path': str(SOURCE), 'snapshot_id': SOURCE.name,
                'parent_source_path': str(parent), 'parent_plan': pin(parent_plan),
                'purpose': 'unchanged r14 pi05 contact, budgets, public verifier and stop rules; locked v3 private labels',
                'public_controller_byte_identical': True, 'private_truth_registration': 'grasp_truth_v3_1153_20261009',
                'files': [{**pin(SOURCE / p), 'relative_path': p} for p in paths]}
            (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(snapshot, indent=2) + '\n')
            archive = SOURCE.with_suffix('.tar')
            with tarfile.open(archive, 'x') as stream:
                for child in SOURCE.iterdir():
                    stream.add(child, arcname=child.name)
            snapshot['archive'] = {**pin(archive), 'archive_complete': True}
        elif str(parent) != snapshot['parent_source_path']:
            raise ValueError('all pi05 controls must use their original common snapshot')
        indexed = {c['name']: c for c in plan['cases']}
        plan['cases'] = [indexed[r['case']] for r in selected]
        for case in plan['cases']:
            old = next(r for r in selected if r['case'] == case['name'])
            if case['state_sha256'] != old['state_sha256']:
                raise ValueError('registered state changed')
            case['paired_baseline_case'] = case['name']
            case['name'] += '_r14_pi05_locked_v3'
        prep = OUT / ('pi05_' + category + '_reference') / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        plan.update(source_path=str(SOURCE), source_snapshot=snapshot, source_commit=SOURCE.name,
            adapter_path=str(ADAPTER), producer=pin(producer), parent_plan=pin(parent_plan),
            producer_dependencies=[pin(producer), *[pin(ADAPTER / 'scripts' / name) for name in (
                'probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
                'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
            references=[*plan['references'], pin(parent_plan), pin(BASELINE)],
            purpose=snapshot['purpose'], qualification_authorized=False,
            training_allowed=False, confirmation=False, new_training_rows=0,
            pi05_handoff_and_budget_unchanged=True)
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env,
                                 capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
        checked.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                                   env=env, capture_output=True, text=True, check=True)
        receipt = {'name': prep.parent.name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
            'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout, 'qualification_allowed': False,
            'training_allowed': False, 'private_truth_rule_unchanged': True,
            'public_controller_byte_identical_to_r14': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'category': category, 'startup_job': receipt['startup_job'], 'source': str(SOURCE)}), flush=True)


if __name__ == '__main__':
    main()
