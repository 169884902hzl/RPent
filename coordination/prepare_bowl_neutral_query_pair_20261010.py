"""Repair the colour-restricted empty-query retry on the same bowl selection pool."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT_PLAN = ROOT / 'results/harness_v5/servo_only_fiveclass_selection_20261010_r1/bowl_analytic/preparation/selection.json'
SOURCE = ROOT / 'source_v5_bowl_neutral_query_20261010_r1'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7/bowl_neutral_query'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
TEST = ROOT / 'coordination/bowl_query_staging_20261010/test_v5_runtime.py'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = copy.deepcopy(json.loads(PARENT_PLAN.read_text()))
    parent = Path(plan['source_path'])
    shutil.copytree(parent, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    path = SOURCE / 'robots/libero/v5_runtime.py'
    text = path.read_text()
    old = '        "bowl": "black bowl on the tabletop",\n'
    if text.count(old) != 1:
        raise ValueError('registered bowl retry prompt changed')
    text = text.replace(old, '        "bowl": "bowl",\n')
    old = '                self.calls += 1\n                masks = []\n'
    if text.count(old) != 1:
        raise ValueError('registered secondary query path changed')
    text = text.replace(old, '                self.calls += 1\n'
        '                if name == "bowl" and not second_reply.get("instances"):\n'
        '                    second_reply = self.rpc.call("sam3.segment_all", kwargs={\n'
        '                        "image_base64": secondary_image, "text_prompt": segmentation_retry_prompt(name),\n'
        '                        "min_score": .35}, timeout_s=120)\n'
        '                    self.calls += 1\n                masks = []\n')
    compile(text, str(path), 'exec')
    path.write_text(text)
    staged = TEST.read_text()
    node = next(n for n in ast.parse(staged).body if isinstance(n, ast.FunctionDef)
                and n.name == 'test_empty_black_bowl_query_recovers_visible_uncoloured_bowl')
    function = '\n'.join(staged.splitlines()[node.lineno-1:node.end_lineno])
    test = SOURCE / 'tests/unit_tests/robots/libero/test_v5_runtime.py'
    with test.open('a') as stream:
        stream.write('\n\n' + function + '\n')
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
               'tests/unit_tests/robots/libero/test_v5_runtime.py::test_empty_black_bowl_query_recovers_visible_uncoloured_bowl']
    checked = subprocess.run(command, cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
        capture_output=True, text=True)
    (SOURCE / 'CPU_bowl_neutral_query.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']]
                     + ['robots/libero/v5_runtime.py', 'tests/unit_tests/robots/libero/test_v5_runtime.py']))
    identity = {**plan['source_snapshot'], 'path': str(SOURCE), 'snapshot_id': SOURCE.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'neutral bowl fallback in both empty views; analytic control and v3 predicate unchanged',
        'CPU_validation': {'command': command, 'output': checked.stdout},
        'files': [{**pin(SOURCE / relative), 'relative_path': relative} for relative in relatives]}
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in SOURCE.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    prep = OUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    shutil.copyfile(Path(__file__), producer)
    previous_producer = plan['producer']['path']
    plan.update(source_path=str(SOURCE), source_snapshot=identity, source_commit=SOURCE.name,
        parent_plan=pin(PARENT_PLAN), producer=pin(producer), purpose=identity['purpose'])
    plan['producer_dependencies'] = [pin(producer), *[r for r in plan['producer_dependencies']
                                                    if r['path'] != previous_producer]]
    for case in plan['cases']:
        case['name'] = case['paired_baseline_case'] + '_bowl_neutral_query'
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env,
                             capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                               env=env, capture_output=True, text=True, check=True)
    receipt = {'name': OUT.name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout,
        'qualification_allowed': False, 'training_allowed': False, 'private_truth_rule_unchanged': True}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'startup_job': receipt['startup_job'], 'source': str(SOURCE)}), flush=True)


if __name__ == '__main__':
    main()
