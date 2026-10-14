"""Pin public two-pad measurements on existing perturbation selection states."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT/'source_v5_grasp_public_tracking_r7_20261010_r1'
SOURCE = ROOT/'source_v5_grasp_public_pad_r8_20261010_r1'
STAGING = ROOT/'coordination/public_pad_r8_staging'
ADAPTER = ROOT/'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT/'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
OUT = ROOT/'results/harness_v5/public_grasp_pad_r8_selection_20261010_r3'
PYTHON = ROOT/'.venv/bin/python'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare_source():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('robots/libero/v5_grasp_public_tracking.py',
                     'scripts/probe_v5_gripper513_calibration_cpu.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'):
        shutil.copyfile(STAGING/relative, SOURCE/relative)
    runtime_path = SOURCE/'robots/libero/v5_runtime.py'
    runtime = runtime_path.read_text()
    for name in ('first', 'second'):
        old = f"            {name}['body_quat_xyzw'] = self.p.env.raw_obs()['robot0_eef_quat'].tolist()\n"
        if runtime.count(old) != 1:
            raise ValueError('unexpected parent runtime grasp frame layout')
        runtime = runtime.replace(old, old + f'            self._measure_grasp_pad_regions({name}, before)\n')
    method = (STAGING/'runtime_pad_measurement_method.txt').read_text()
    marker = '    def verify_grasp_measurement(self, before: Entity) -> bool | None:\n'
    if runtime.count(marker) != 1:
        raise ValueError('unexpected parent runtime verification layout')
    runtime_path.write_text(runtime.replace(marker, method + marker))
    env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1',
               LIBERO_TYPE='standard', LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),
               OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    checks = subprocess.run([str(PYTHON), '-m', 'pytest',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py',
        'tests/unit_tests/robots/libero/test_v5_category_contact_anchor.py', '-q'],
        cwd=SOURCE, env=env, text=True, capture_output=True)
    (SOURCE/'CPU_public_pad_r8.log').write_text(checks.stdout+checks.stderr)
    checks.check_returncode()
    calibration_dir = OUT/'robot_geometry_CPU'
    measure = subprocess.run([str(PYTHON), '-m', 'scripts.probe_v5_gripper513_calibration_cpu',
        '--manifest', str(ROOT/'results/harness_v5/grasp451_sustained_truth_20261005/preparation/smoke.json'),
        '--enrich-existing', str(ROOT/'results/harness_v5/gripper513_original_opening_calibration_20261005/cpu_run2/report.json'),
        '--output', str(calibration_dir)], cwd=SOURCE, env=env, text=True, capture_output=True)
    (SOURCE/'CPU_robot_geometry_r8.log').write_text(measure.stdout+measure.stderr)
    measure.check_returncode()
    calibration = pin(calibration_dir/'report.json')
    identity = json.loads((PARENT/'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
        purpose='measure each public finger pad with signed robot joints; verdict and locked private truth unchanged',
        public_tracking_source=pin(SOURCE/'robots/libero/v5_grasp_public_tracking.py'),
        CPU_validation={'command': checks.args, 'output': checks.stdout},
        original_robot_geometry=calibration)
    for record in identity['files']:
        record.update(pin(SOURCE/record['relative_path']))
    (SOURCE/'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2)+'\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    archive_pin = {**pin(archive), 'archive_complete': True}


if not SOURCE.exists():
    prepare_source()
identity = json.loads((SOURCE/'source_identity_v3r9.json').read_text())
for relative in ('robots/libero/v5_grasp_public_tracking.py', 'scripts/probe_v5_gripper513_calibration_cpu.py'):
    if pin(SOURCE/relative)['sha256'] != pin(STAGING/relative)['sha256']:
        raise ValueError('prepared source differs from staging')
calibration = identity['original_robot_geometry']
if pin(Path(calibration['path']))['sha256'] != calibration['sha256']:
    raise ValueError('original robot geometry calibration changed')
report = json.loads(Path(calibration['path']).read_text())
calibration_payload = {key: report[key] for key in
    ('opening_calibration', 'grip_site_geometry', 'robot_rigid_transform_validation')}
archive_pin = {**pin(SOURCE.with_suffix('.tar')), 'archive_complete': True}
bases = [('bottle', 'analytic', ROOT/'results/harness_v5/perturb_contact_methods_selection_20261009_r1/grasp_bottle_analytic/preparation/selection.json'),
         ('bottle', 'pi05', ROOT/'results/harness_v5/perturb_contact_methods_selection_20261009_r3/grasp_bottle_pi05/preparation/selection.json'),
         ('cup', 'pi05', ROOT/'results/harness_v5/perturb_contact_methods_selection_20261009_r3/grasp_cup_pi05/preparation/selection.json')]
for _, _, base in bases:
    if not base.is_file():
        raise FileNotFoundError(base)
for category, method, base in bases:
    plan = copy.deepcopy(json.loads(base.read_text()))
    if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
        raise ValueError('existing selection100 required')
    prep = OUT/f'{category}_{method}'/'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep/'producer.py'
    shutil.copyfile(Path(__file__), producer)
    old_producer_path = plan['producer']['path']
    plan['producer'] = pin(producer)
    plan.update(source_path=str(SOURCE), adapter_path=str(ADAPTER), source_commit=identity['snapshot_id'],
        source_snapshot={**identity, 'path': str(SOURCE), 'commit': identity['snapshot_id'], 'archive': archive_pin},
        parent_plan=pin(base), qualification_authorized=False,
        purpose='public contact measurement development on original perturbation selection; no verifier threshold chosen',
        new_evidence_replay=True, new_training_rows=0)
    plan['references'].append(calibration)
    for record in plan['producer_dependencies']:
        old = Path(record['path'])
        new = ADAPTER/'scripts'/old.name
        if str(old) == old_producer_path:
            record.update(pin(producer))
        elif '/scripts/' in str(old) and 'adapter_' in str(old) and new.exists():
            record.update(pin(new))
    for condition in plan['conditions'].values():
        condition.setdefault('overrides', {}).update(grasp_public_tracking_v1=True,
            grasp_public_coupled_lift_v1=True, grasp_independent_views_v1=True,
            grasp_measurement_calibration=calibration_payload)
    for case in plan['cases']:
        case['name'] += '_public_pad_r8'
    path = prep/'selection.json'
    path.write_text(json.dumps(plan, indent=2)+'\n')
    task_env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    cpu = subprocess.run(['bash', str(LAUNCH)], env=task_env, text=True, capture_output=True)
    (prep/'CPU_preflight.log').write_text(cpu.stdout+cpu.stderr)
    cpu.check_returncode()
    task_env['PERTURB_SKILL_CPU_ONLY'] = '0'
    job = subprocess.run(['sbatch', '--parsable', '--export=ALL', str(LAUNCH)],
        env=task_env, text=True, capture_output=True, check=True).stdout.strip()
    receipt = {'name': prep.parent.name, 'startup_job': job, 'plan': pin(path), 'launcher': pin(LAUNCH),
               'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
               'verifier_verdict_unchanged': True, 'new_public_measurements_only': True}
    (prep/'submission.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
