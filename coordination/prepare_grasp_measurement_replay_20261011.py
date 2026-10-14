"""Prepare private development replays; do not alter closed confirmation ledgers."""
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
OUT = ROOT / 'results/harness_v5/grasp_measurement_development_20261011_r4'
PAYLOAD = ROOT / 'coordination/grasp_measurement_patch_20261011_r1'
LAUNCH = ROOT / 'coordination/run_v5_grasp_measurement_development_20261011.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def function_span(body, name):
    node = next(n for n in ast.parse(body).body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = body.splitlines(keepends=True)
    return sum(map(len, lines[:node.lineno-1])), sum(map(len, lines[:node.end_lineno]))


def main():
    # Trace adapter already includes begin/finally-finish for both contact methods.
    adapter = ROOT / 'coordination/perturb_measurement_adapter_20261011_r4'
    shutil.copytree(ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9_trace_r1', adapter,
                    ignore=shutil.ignore_patterns('__pycache__'))
    path = adapter / 'scripts/probe_v5_skill501_original.py'
    body = path.read_text()
    desired = (PAYLOAD / 'probe_v5_skill501_original.py').read_text()
    for name in ('attach_skill_grasp_trace','execute_stage'):
        a,b=function_span(body,name)
        c,d=function_span(desired,name)
        body=body[:a]+desired[c:d]+body[b:]
    marker='            self._rpc[\"oracle.skill501_grasp_trace_begin\"] = self.grasp_trace_begin\n'
    body=body.replace(marker,marker+"            self._rpc['oracle.skill501_grasp_trace_reference'] = lambda: to_numpy_tree(self._env.env.workers[0].env_call('v5_skill501_grasp_trace_reference',target='self'))\n")
    body=body.replace('log_path=str(output / "oracle_env.log"))',
                      'log_path=str(output / "oracle_env.log"), cwd="/tmp")')
    compile(body, str(path), 'exec')
    path.write_text(body)
    replay_index = ROOT / 'coordination/grasp_closed_measurement_diagnosis_20261011_r1/development_replay_cases.jsonl'
    items = list(map(json.loads, replay_index.read_text().splitlines()))
    receipts = []
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        prior = ROOT / f'results/harness_v5/geometric_grasp_confirmation_20261010_r1/{category}/preparation/confirmation.json'
        plan = copy.deepcopy(json.loads(prior.read_text()))
        source = ROOT / f'source_v5_measurement_development_20261011_r4_{category}'
        shutil.copytree(Path(plan['source_path']), source, symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.git', '.venv',
                                                      'results', 'coordination', 'artifacts', 'assets', 'docs'))
        # Only private measurements change. Public controller modules are copied byte-for-byte.
        shutil.copyfile(PAYLOAD / 'v5_grasp_truth.py', source / 'robots/libero/v5_grasp_truth.py')
        # The subprocess and worker must resolve the very same diagnostic
        # module even if a library changes its child working directory.
        shutil.copyfile(path,source/'scripts/probe_v5_skill501_original.py')
        identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
                    'parent_source_path': plan['source_path'], 'parent_plan': pin(prior),
                    'purpose': 'full control trace and automatic initial support; diagnostic only',
                    'public_controller_byte_identical': True,
                    'private_support_version': 'initial-contact-geometries/1-dev',
                    'files': [{**pin(source/f['relative_path']), 'relative_path': f['relative_path']}
                              for f in plan['source_snapshot']['files']]}
        (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2)+'\n')
        archive = source.with_suffix('.tar')
        with tarfile.open(archive, 'x') as stream:
            for child in source.iterdir():
                stream.add(child, arcname=child.name)
        identity['archive'] = {**pin(archive), 'archive_complete': True}
        plan.update(cohort='selection', confirmation=False, training_allowed=False,
                    source_path=str(source), source_snapshot=identity, adapter_path=str(adapter),
                    purpose='closed failed/unknown states replayed for measurement diagnosis only',
                    qualification_authorized=False, new_training_rows=0,
                    closed_confirmation_scores_unchanged=True,
                    producer=pin(Path(__file__)), parent_plan=pin(prior), diagnostic_failed_case_replay_only=True,
                    producer_dependencies=[pin(Path(__file__)), *[pin(adapter/'scripts'/name) for name in (
                        'probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
                        'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]])
        selected = [x for x in items if x['index']['group']==category]
        selected.sort(key=lambda x:x['index']['physically_executed'] is not True)
        plan['cases'] = []
        for item in selected:
            case = copy.deepcopy(item['case'])
            case.update(name=case['name']+'_measurement_dev', confirmation=False,
                        training_allowed=False, permanent_training_exclusion=True,
                        diagnostic_closed_case=item['index'])
            plan['cases'].append(case)
        for condition in plan['conditions'].values():
            condition.setdefault('overrides', {})['motion_trace_v1'] = True
        prep = OUT/category/'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        dest = prep/'selection.json'
        dest.write_text(json.dumps(plan, indent=2)+'\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(dest), PERTURB_SKILL_PLAN_SHA=pin(dest)['sha256'],
                   PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=str(adapter),
                   PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        check = subprocess.run(['bash',str(LAUNCH)],env=env,cwd='/tmp',capture_output=True,text=True)
        (prep/'CPU_preflight.log').write_text(check.stdout+check.stderr)
        check.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY']='0'
        submission = subprocess.run(['sbatch','--parsable','--exclude=node02','--nice=500','--time=00:30:00',
                                     '--chdir=/tmp','--export=ALL',str(LAUNCH)],env=env,
                                    capture_output=True,text=True,check=True)
        receipt = {'startup_job':submission.stdout.strip(), 'plan':pin(dest), 'launcher':pin(LAUNCH),
                   'cases':len(plan['cases']), 'resource_rules':{'exclude':'node02','nice':500},
                   'closed_confirmation_reopened':False, 'training_allowed':False}
        (prep/'startup_submission.json').write_text(json.dumps(receipt,indent=2)+'\n')
        receipts.append(receipt)
        print(json.dumps({'category':category,**receipt}),flush=True)
    (OUT/'startup_manifest.json').write_text(json.dumps(receipts,indent=2)+'\n')


if __name__=='__main__':
    main()
