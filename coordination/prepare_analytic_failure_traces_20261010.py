"""Replay original failed selection cases with read-only motion/contact instrumentation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/servo_only_fiveclass_selection_20261010_r1'
OUT = ROOT / 'results/harness_v5/analytic_failure_phases_selection_20261010_r1'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9_trace_r1'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


attempts = ROOT / 'artifacts/contact_methods_intermediate_20261009_r14/attempts.jsonl'
old = {r['case']: r for r in map(json.loads, attempts.open())}
sources = {}
for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
    prior = BASE / (category + '_analytic') / 'preparation/selection.json'
    plan = copy.deepcopy(json.loads(prior.read_text()))
    plan['cases'] = [c for c in plan['cases'] if
        (old[c['paired_baseline_case']]['failure_reason'] == 'analytic_descend_not_reached' or
         (old[c['paired_baseline_case']]['private_success'] is False
          and old[c['paired_baseline_case']]['failure_reason'] is None))]
    parent = Path(plan['source_path'])
    if parent not in sources:
        source = ROOT / ('source_v5_analytic_failure_traces_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
        shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
        path = source / 'robots/libero/v5_analytic_grasp.py'; body = path.read_text()
        token = 'gripper=-1., tol=.008, ori_tol=.05, max_steps=150)'
        if body.count(token) != 1:
            raise ValueError('must instrument exactly the original pose servo')
        body = body.replace(token, 'gripper=-1., tol=.008, ori_tol=.05, max_steps=150,\n'
            '                                     trace_steps=True, motion_diagnostic=lambda: executor.p.env._client.call(\n'
            '                                         "diagnostic.motion", timeout_s=30))')
        compile(body, str(path), 'exec'); path.write_text(body)
        identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
                    'parent_identity': pin(parent / 'source_identity_v3r9.json'),
                    'purpose': 'r14 controls unchanged; read-only pose-servo trace enabled',
                    'no_control_parameter_changes': True,
                    'files': [{**pin(source / f['relative_path']), 'relative_path': f['relative_path']}
                              for f in plan['source_snapshot']['files']]}
        (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
        archive = source.with_suffix('.tar')
        with tarfile.open(archive, 'x') as stream:
            for child in source.iterdir():stream.add(child, arcname=child.name)
        identity['archive'] = {**pin(archive), 'archive_complete': True}
        sources[parent] = source, identity
    source, identity = sources[parent]
    prep = OUT / (category + '_analytic') / 'preparation'; prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'; shutil.copyfile(Path(__file__), producer)
    plan.update(source_path=str(source), source_snapshot=identity, adapter_path=str(ADAPTER),
        producer=pin(producer), producer_dependencies=[pin(producer), *[pin(ADAPTER/'scripts'/name) for name in (
            'probe_v5_skill501_original.py','probe_v5_perturb_skill_20261009.py',
            'v5_perturb_goal_diagnostic.py','v5_perturb_public_reference.py')]],
        parent_plan=pin(prior), diagnostic_failed_case_replay_only=True,
        diagnostic_selection_uses_old_outcomes=True,
        purpose='failure-cause diagnosis, not method ranking; old physical records retained')
    for case in plan['cases']:
        case['name'] = case['paired_baseline_case'] + '_diagnostic_trace'
    path = prep / 'selection.json'; path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    check = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
    (prep/'CPU_preflight.log').write_text(check.stdout+check.stderr); check.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY']='0'
    result = subprocess.run(['sbatch','--parsable','--chdir=/tmp','--export=ALL',str(LAUNCH)],
                            env=env,capture_output=True,text=True,check=True)
    receipt={'startup_job':result.stdout.strip(), 'plan':pin(path), 'launcher':pin(LAUNCH),
             'selected_failure_states':len(plan['cases']), 'purpose':plan['purpose'],
             'qualification_allowed':False,'training_allowed':False}
    (prep/'submission.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'category':category,**receipt}),flush=True)
