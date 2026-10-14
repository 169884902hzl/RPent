"""Isolate public target tracking on the first eight registered bottle layouts."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_contact_methods_20261009_r5'
SOURCE = ROOT / 'source_v5_grasp_public_tracking_20261009_r1'
PREVIOUS = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r2/grasp_bottle_analytic/preparation/selection.json'
OUTPUT = ROOT / 'results/harness_v5/grasp_public_tracking_pilot8_20261009_r1/grasp_bottle_analytic_tracking'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent source changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    text = runtime.read_text()
    changes = [
        ('        grasp_independent_views_v1: bool = False,',
         '        grasp_independent_views_v1: bool = False,\n        grasp_public_tracking_v1: bool = False,'),
        ('        self.grasp_independent_views_v1 = grasp_independent_views_v1',
         '        self.grasp_independent_views_v1 = grasp_independent_views_v1\n'
         '        self.grasp_public_tracking_v1 = grasp_public_tracking_v1\n'
         '        self.grasp_public_closing_xyz = None'),
        ('        first = self.independent_grasp_frame(before, height)',
         '        tracking = self.grasp_public_tracking_v1 and self.grasp_public_closing_xyz is not None\n'
         '        if tracking:\n'
         '            from robots.libero.v5_grasp_public_tracking import refresh_grasp_target\n'
         '            tracking_first = refresh_grasp_target(self, before, self.grasp_public_closing_xyz)\n'
         '        first = self.independent_grasp_frame(before, height)'),
        ('        self._refresh([before.name])\n        second = self.independent_grasp_frame(before, height)',
         '        if tracking:\n'
         '            tracking_second = refresh_grasp_target(self, before, self.grasp_public_closing_xyz)\n'
         '            self.last_verification_measurements["public_target_tracking"] = [tracking_first, tracking_second]\n'
         '        else:\n            self._refresh([before.name])\n'
         '        second = self.independent_grasp_frame(before, height)'),
        ('        self._grasp_occlusion_scan_used = False\n        self.motion_evidence = []',
         '        self._grasp_occlusion_scan_used = False\n        self.grasp_public_closing_xyz = None\n'
         '        self.motion_evidence = []')]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('runtime tracking anchor changed')
        text = text.replace(old, new)
    runtime.write_text(text)
    entry = SOURCE / 'harness_v5_eval.py'
    text = entry.read_text().replace(
        '                             grasp_independent_views_v1=getattr(args, "grasp_independent_views_v1", False),',
        '                             grasp_independent_views_v1=getattr(args, "grasp_independent_views_v1", False),\n'
        '                             grasp_public_tracking_v1=getattr(args, "grasp_public_tracking_v1", False),')
    text = text.replace('    parser.add_argument("--analytic-grasp-v1", action="store_true")',
        '    parser.add_argument("--analytic-grasp-v1", action="store_true")\n'
        '    parser.add_argument("--grasp-public-tracking-v1", action="store_true")')
    entry.write_text(text)
    changed = ['robots/libero/v5_runtime.py', 'harness_v5_eval.py', 'robots/libero/v5_analytic_grasp.py',
        'robots/libero/v5_grasp_public_tracking.py', 'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py']
    for relative in changed[2:]:
        shutil.copy2(ROOT / relative, SOURCE / relative)
    with tarfile.open(parent['archive']['path']) as archive:
        names = list(dict.fromkeys([*archive.getnames(), *changed]))
    target = Path(str(SOURCE) + '.tar')
    with tarfile.open(target, 'x') as archive:
        for relative in names:
            archive.add(SOURCE / relative, arcname=relative, recursive=False)
    file_names = [r['relative_path'] for r in parent['files']]
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(target),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in dict.fromkeys([*file_names, *changed])],
        'purpose': 'public translation-gated RGB-D identity pilot; contact waypoints/parameters unchanged'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    prep = OUTPUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    producer.write_bytes(Path(__file__).read_bytes())
    plan = json.loads(PREVIOUS.read_text())
    cases = [{**case, 'name': case['name'] + '_tracking', 'condition': 'analytic_tracking'}
             for case in plan['cases'][:8]]
    condition = plan['conditions']['analytic']
    condition['overrides']['grasp_public_tracking_v1'] = True
    adapter = ROOT / 'coordination/perturb_contact_methods_adapter_20261009_r5'
    plan.update(source_path=str(SOURCE), source_snapshot=snapshot, adapter_path=str(adapter),
        cases=cases, conditions={'analytic_tracking': condition}, method='analytic_tracking',
        producer=ref(producer), producer_dependencies=[ref(producer),
            *[ref(adapter / 'scripts' / name) for name in ('probe_v5_skill501_original.py',
                'probe_v5_perturb_skill_20261009.py', 'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
        references=[*plan['references'], ref(PREVIOUS)],
        purpose='first8 public-identity pilot, not qualification; no Pi0.5 handoff changes',
        diagnostic_contact_trajectory=True, layout_states=8)
    manifest = prep / 'selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
        'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(adapter),
        'PERTURB_SKILL_OUTPUT': str(OUTPUT), 'PERTURB_SKILL_STARTUP': '1'}
    launcher = adapter / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    cpu = subprocess.run(['bash', str(launcher)], env={**os.environ, **env,
        'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    job = subprocess.check_output(['sbatch', '--parsable', '--array=0', '--nice=0',
        '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)], text=True).strip()
    record = {'job': job, 'environment': env, 'manifest': ref(manifest), 'launcher': ref(launcher),
        'physical_startup': 'pending', 'confirmation': False}
    (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
