"""Measure precise analytic contact on the unchanged bowl/pan selection pools."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_analytic_contact_precision_r12_20261010_r2'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCHER = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
OUT = ROOT / 'results/harness_v5/analytic_contact_precision_bowl_pan_selection_20261010_r1'
PARENTS = {
    'bowl_analytic': ROOT / 'results/harness_v5/public_grasp_pose_r6_selection_20261010/bowl_analytic_reference/preparation/selection.json',
    'pan_analytic': ROOT / 'results/harness_v5/registered_grasp_v3r9_selection_20261010/pan_analytic_handle/preparation/selection.json',
}


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    identity = json.loads((SOURCE / 'source_identity_v3r9.json').read_text())
    for name, parent in PARENTS.items():
        plan = copy.deepcopy(json.loads(parent.read_text()))
        if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
            raise ValueError('unchanged registered selection100 required')
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        prior_producer = plan['producer']['path']
        prior_source = Path(plan['source_path'])
        plan.update(producer=pin(producer), source_path=str(SOURCE), source_commit=SOURCE.name,
            source_snapshot={**identity, 'path': str(SOURCE), 'commit': SOURCE.name,
                'archive': {**pin(SOURCE.with_suffix('.tar')), 'archive_complete': True}},
            adapter_path=str(ADAPTER), parent_plan=pin(parent), qualification_authorized=False,
            purpose='precise analytic contact on original perturbation selection; no confirmation qualification',
            new_evidence_replay=True, new_training_rows=0)
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if str(path) == prior_producer:
                record.update(pin(producer))
            elif path.is_relative_to(prior_source):
                record.update(pin(SOURCE / path.relative_to(prior_source)))
        for case in plan['cases']:
            if not case.get('registered_layout_state'):
                raise ValueError('selection layout provenance missing')
            if pin(Path(case['registered_layout_state']['path'])) != case['registered_layout_state']:
                raise ValueError('selection state changed')
            case['name'] += '_contact_precision_r12'
        for condition in plan['conditions'].values():
            condition.setdefault('overrides', {}).update(analytic_contact_precision_v1=True,
                grasp_public_tracking_v1=True, grasp_public_coupled_lift_v1=True,
                grasp_independent_views_v1=True, motion_trace_v1=True)
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCHER)], cwd='/tmp', env=env, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCHER)],
            env=env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': result.stdout.strip(), 'plan': pin(path),
            'launcher': pin(LAUNCHER), 'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
            'public_rgbd_storage_dtype': 'float32', 'public_verdict_rule_unchanged': True,
            'analytic_contact_precision_v1': True, 'training_allowed': False}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
