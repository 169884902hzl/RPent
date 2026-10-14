"""Use precompiled public source language on the original bowl selection pool."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_grasp_public_pose_r6_20261010_r1'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
PARENT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r3/grasp_bowl_pi05/preparation/selection.json'
OUT = ROOT / 'results/harness_v5/public_grasp_pose_r6_selection_20261010/bowl_analytic_reference'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


plan = copy.deepcopy(json.loads(PARENT.read_text()))
if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
    raise ValueError('original selection100 required')
identity = json.loads((SOURCE / 'source_identity_v3r9.json').read_text())
conditions = {'analytic_public_reference': {
    'executor': 'current', 'max_chunks': 160, 'overrides': {
        'dual_view_fusion_v1': True, 'measured_action_receipts_v1': True,
        'skill_budget_v1': True, 'task_completion_receipts_v1': True,
        'analytic_grasp_v1': True, 'grasp_public_tracking_v1': True,
        'grasp_public_coupled_lift_v1': True, 'grasp_independent_views_v1': True}}}
for case in plan['cases']:
    state_path = Path(case['registered_layout_state']['path'])
    if pin(state_path) != case['registered_layout_state']:
        raise ValueError('registered selection layout changed')
    state = json.loads(state_path.read_text())
    if not case.get('compiled_public_instruction') or case['subtask_prompt'] != state['diagnostic_instruction']:
        raise ValueError('use the existing outcome-independent public reference')
    case.update(name=case['name'].removesuffix('_pi05') + '_analytic_public_reference',
                condition='analytic_public_reference')
archive = SOURCE.with_suffix('.tar')
plan.update(source_path=str(SOURCE), source_commit=identity['snapshot_id'],
    source_snapshot={**identity, 'path': str(SOURCE), 'commit': identity['snapshot_id'],
                     'archive': {**pin(archive), 'archive_complete': True}},
    adapter_path=str(ADAPTER), conditions=conditions, parent_plan=pin(PARENT),
    purpose='original selection100 with precompiled public source disambiguation; no confirmation qualification',
    qualification_authorized=False, new_evidence_replay=True, new_training_rows=0)
for record in plan['producer_dependencies']:
    old = Path(record['path'])
    new = ADAPTER / 'scripts' / old.name
    if '/scripts/' in str(old) and 'adapter_' in str(old) and new.exists():
        record.update(pin(new))
prep = OUT / 'preparation'
prep.mkdir(parents=True, exist_ok=False)
path = prep / 'selection.json'
path.write_text(json.dumps(plan, indent=2) + '\n')
env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
    PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
    PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
check = subprocess.run(['bash', str(LAUNCH)], env=env, text=True, capture_output=True)
(prep / 'CPU_preflight.log').write_text(check.stdout + check.stderr)
check.check_returncode()
env['PERTURB_SKILL_CPU_ONLY'] = '0'
job = subprocess.run(['sbatch', '--parsable', '--export=ALL', str(LAUNCH)],
    env=env, text=True, capture_output=True, check=True).stdout.strip()
receipt = {'name': OUT.name, 'startup_job': job, 'plan': pin(path), 'launcher': pin(LAUNCH),
           'CPU_preflight': check.stdout, 'qualification_allowed': False,
           'physical_selection_states_unchanged': True}
(prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
