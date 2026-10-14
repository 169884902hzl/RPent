"""Pin current contact and analytic contact on the same 100 selection layouts."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_public_references_20261009_r1'
SOURCE = ROOT / 'source_v5_contact_methods_20261009_r2'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261009_r2'
OLD_ADAPTER = ROOT / 'coordination/perturb_public_reference_adapter_20261009_r1'
PREVIOUS = ROOT / 'results/harness_v5/perturb_grasp_public_reference_20261009_r2'
OUTPUT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r2'


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def create_source():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    archive = Path(parent['archive']['path'])
    if ref(archive) != parent['archive']:
        raise ValueError('parent archive changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    text = runtime.read_text()
    replacements = [
        ('        grasp_wrist_contact_v3: bool = False,',
         '        grasp_wrist_contact_v3: bool = False,\n        analytic_grasp_v1: bool = False,'),
        ('        self.grasp_wrist_contact_v3 = grasp_wrist_contact_v3',
         '        self.grasp_wrist_contact_v3 = grasp_wrist_contact_v3\n        self.analytic_grasp_v1 = analytic_grasp_v1'),
        ('                self.scene.region_anchors.pop(obj.id, None)\n            if self.grasp_category_profiles_v1',
         '                self.scene.region_anchors.pop(obj.id, None)\n'
         '            if self.analytic_grasp_v1:\n'
         '                from robots.libero.v5_analytic_grasp import execute_analytic_grasp\n'
         '                if self.target_cache_v1:\n'
         '                    self.target_cache = {e.id: e for e in self.scene.entities.values()\n'
         '                                         if e.visible and e.id != obj.id and e.name != obj.name}\n'
         '                execute_analytic_grasp(self, obj, receipt)\n'
         '                return\n            if self.grasp_category_profiles_v1')]
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('unexpected runtime parent anchor')
        text = text.replace(old, new)
    runtime.write_text(text)
    entry = SOURCE / 'harness_v5_eval.py'
    text = entry.read_text().replace('"grasp_wrist_contact_v3", "grasp_rim_v1"',
                                   '"grasp_wrist_contact_v3", "analytic_grasp_v1", "grasp_rim_v1"')
    text = text.replace('    parser.add_argument("--grasp-wrist-contact-v3", action="store_true")',
                        '    parser.add_argument("--grasp-wrist-contact-v3", action="store_true")\n'
                        '    parser.add_argument("--analytic-grasp-v1", action="store_true")')
    entry.write_text(text)
    changed = ['robots/libero/v5_runtime.py', 'harness_v5_eval.py',
               'robots/libero/v5_analytic_grasp.py', 'scripts/probe_v5_skill501_original.py',
               'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py']
    for relative in changed[2:]:
        shutil.copy2(ROOT / relative, SOURCE / relative)
    with tarfile.open(archive) as stream:
        members = list(dict.fromkeys([*stream.getnames(), *changed]))
    target = Path(str(SOURCE) + '.tar')
    with tarfile.open(target, 'x') as stream:
        for relative in members:
            stream.add(SOURCE / relative, arcname=relative, recursive=False)
    with tarfile.open(target) as stream:
        for relative in changed:
            if hashlib.sha256(stream.extractfile(relative).read()).hexdigest() != ref(SOURCE / relative)['sha256']:
                raise ValueError('archive/source mismatch')
    names = [str(i.get('relative_path') or Path(i['path']).relative_to(PARENT)) for i in parent['files']]
    snapshot = {'path': str(SOURCE), 'commit': parent['commit'],
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'), 'archive': ref(target),
        'archive_complete': True, 'archive_member_count': len(members),
        'modified_modules_in_archive_verified': True,
        'files': [{**ref(SOURCE / n), 'relative_path': n} for n in dict.fromkeys([*names, *changed])],
        'purpose': 'public analytic contact vs unchanged Pi0.5 contact; matched diagnostic chunk function'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    shutil.copytree(OLD_ADAPTER, ADAPTER, ignore=shutil.ignore_patterns('__pycache__'))
    # The adapter calls stop_on_native; its pinned runner now implements it.
    shutil.copy2(ROOT / 'scripts/probe_v5_skill501_original.py', ADAPTER / 'scripts/probe_v5_skill501_original.py')
    return snapshot


def main():
    snapshot = create_source()
    launcher = ADAPTER / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    for category in ('bowl', 'bottle', 'box', 'cup', 'frypan'):
        old_path = PREVIOUS / ('grasp_' + category) / 'preparation/selection.json'
        old = json.loads(old_path.read_text())
        original = [c for c in old['cases'] if c['condition'] == 'current_public_reference160']
        if len(original) != 100:
            raise ValueError('exactly 100 registered layouts per class required')
        for method in ('analytic',):
            cell = 'grasp_' + category + '_' + method
            prep = OUTPUT / cell / 'preparation'
            prep.mkdir(parents=True, exist_ok=False)
            condition = copy.deepcopy(old['conditions']['current_public_reference160'])
            condition['overrides']['analytic_grasp_v1'] = method == 'analytic'
            cases = []
            for item in original:
                case = copy.deepcopy(item)
                case.update(name=case['name'].removesuffix('_current_public_reference160') + '_' + method,
                            condition=method)
                if ref(Path(case['registered_layout_state']['path'])) != case['registered_layout_state']:
                    raise ValueError('registered state changed')
                cases.append(case)
            deps = [ref(ADAPTER / 'scripts' / name) for name in (
                'probe_v5_perturb_skill_20261009.py', 'probe_v5_skill501_original.py',
                'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]
            plan = {**old, 'source_path': str(SOURCE), 'source_snapshot': snapshot,
                'source_commit': snapshot['commit'], 'adapter_path': str(ADAPTER),
                'cases': cases, 'conditions': {method: condition}, 'producer': ref(Path(__file__)),
                'producer_dependencies': [ref(Path(__file__)), *deps], 'references': [*old['references'], ref(old_path)],
                'max_chunks': 160, 'method': method,
                'purpose': 'method selection; same layouts/public source sentences, no Pi0.5 handoff tuning',
                'confirmation': False, 'training_allowed': False}
            path = prep / 'selection.json'
            path.write_text(json.dumps(plan, indent=2) + '\n')
            env = {'PERTURB_SKILL_PLAN': str(path), 'PERTURB_SKILL_PLAN_SHA': ref(path)['sha256'],
                'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(ADAPTER),
                'PERTURB_SKILL_OUTPUT': str(OUTPUT / cell), 'PERTURB_SKILL_STARTUP': '1'}
            cpu = subprocess.run(['bash', str(launcher)], env={**os.environ, **env,
                'PERTURB_SKILL_CPU_ONLY': '1'}, text=True, capture_output=True)
            (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
            cpu.check_returncode()
            command = ['sbatch', '--parsable', '--array=0', '--nice=100',
                       '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
            job = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
            record = {'job': job, 'environment': env, 'launcher': ref(launcher),
                'manifest': ref(path), 'CPU_preflight': 'pass', 'physical_startup': 'pending',
                'confirmation': False}
            (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
            print(json.dumps({'cell': cell, 'job': job, 'registered_trials': 100}), flush=True)


if __name__ == '__main__':
    main()
