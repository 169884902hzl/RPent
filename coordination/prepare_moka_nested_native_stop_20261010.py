"""Pin a selection replay that exposes native completion inside a finite skill."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT/'source_v5_moka_native_stop_20261009_r3'
SOURCE = ROOT/'source_v5_moka_nested_native_stop_20261010_r1'
OLD = ROOT/'results/harness_v5/moka_selection100_20261009_r3/preparation'
PREP = ROOT/'results/harness_v5/moka_nested_native_stop_selection100_20261010_r1/preparation'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


shutil.copytree(PARENT, SOURCE, symlinks=True,
                ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
overlays = []
for staged, relative in [
    ('moka_nested_stop_env_staging.py', 'robots/libero/v5_env_client.py'),
    ('moka_nested_stop_probe_staging.py', 'scripts/probe_v5_moka_transfer_public_20261007.py'),
    ('moka_nested_stop_test_env_staging.py', 'tests/unit_tests/robots/libero/test_v5_env_client.py'),
    ('moka_nested_stop_test_binding_staging.py', 'tests/unit_tests/robots/libero/test_v5_moka_public_stove_binding.py'),
]:
    before = pin(SOURCE/relative)
    shutil.copyfile(ROOT/'coordination'/staged, SOURCE/relative)
    overlays.append({'relative_path': relative, 'parent': before, 'installed': pin(SOURCE/relative)})
env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
check = subprocess.run([str(ROOT/'.venv/bin/python'), '-m', 'pytest', '-q',
    'tests/unit_tests/robots/libero/test_v5_env_client.py',
    'tests/unit_tests/robots/libero/test_v5_moka_public_stove_binding.py'],
    cwd=SOURCE, env=env, capture_output=True, text=True)
(SOURCE/'CPU_nested_stop.log').write_text(check.stdout+check.stderr)
check.check_returncode()
PREP.mkdir(parents=True, exist_ok=False)
for name in ['probe_v5_moka_layout24_20261008.py', 'serve_v5_moka_layout24_20261008.py',
             'typed_choice_eval.py', 'preflight.py']:
    shutil.copyfile(OLD/name, PREP/name)
launcher = PREP/'run_selection100.sbatch'
launcher.write_text((OLD/launcher.name).read_text().replace(str(OLD.parent), str(PREP.parent)))
identity = json.loads((OLD/'source_identity.json').read_text())
identity.update(path=str(SOURCE), parent_snapshot=str(PARENT),
    identity_kind='parent_snapshot_plus_nested_native_stop_overlay',
    nested_native_stop_overlay=overlays, CPU_validation={'command': check.args, 'result': check.stdout})
for record in identity['files']:
    record.update(pin(SOURCE/record['relative_path']))
known = {record['relative_path'] for record in identity['files']}
for overlay in overlays:
    if overlay['relative_path'] not in known:
        identity['files'].append({**overlay['installed'], 'relative_path': overlay['relative_path']})
for overlay in identity.get('overlay', []):
    old_path = Path(overlay['installed']['path'])
    overlay['installed'].update(pin(SOURCE/old_path.relative_to(PARENT)))
archive = SOURCE.with_suffix('.tar')
with tarfile.open(archive, 'w') as stream:
    for child in SOURCE.iterdir():
        if child.name not in ('__pycache__', '.pytest_cache'):
            stream.add(child, arcname=child.name)
identity['archive'] = pin(archive)
(SOURCE/'source_identity_nested_stop.json').write_text(json.dumps(identity, indent=2)+'\n')
(PREP/'source_identity.json').write_text(json.dumps(identity, indent=2)+'\n')
plan = copy.deepcopy(json.loads((OLD/'selection100.json').read_text()))
if len(plan['cases']) != 100 or plan['qualification_authorized'] or plan['training_allowed']:
    raise ValueError('original development selection100 required')
plan.update(source_snapshot=identity, source_path=str(SOURCE), source_identity=pin(PREP/'source_identity.json'),
    source_snapshot_sha256=hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    producer=pin(Path(__file__)), prior_selection_manifest=pin(OLD/'selection100.json'),
    comparison_parent=str(OLD.parent),
    purpose='same original selection100, native success visible inside outer finite skill; unchanged chunks160',
    new_confirmation_attempts=0, jobs_submitted=[], new_physics_executed_in_preparation=False)
for record in plan['producer_dependencies']:
    old_path = Path(record['path'])
    if old_path.is_relative_to(PARENT):
        record.update(pin(SOURCE/old_path.relative_to(PARENT)))
    elif old_path.is_relative_to(OLD):
        record.update(pin(PREP/old_path.relative_to(OLD)))
for key in ('launcher_identity',):
    if isinstance(plan.get(key), dict):
        plan[key] = pin(launcher)
manifest = PREP/'selection100.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
startup_env = {**json.loads((OLD/'startup_submission.json').read_text())['environment'],
    'MOKA_TRANSFER_SOURCE': str(SOURCE), 'MOKA_TRANSFER_MANIFEST': str(manifest),
    'MOKA_TRANSFER_MANIFEST_SHA': pin(manifest)['sha256']}
check = subprocess.run(['bash', str(launcher)], env={**os.environ, **startup_env,
    'MOKA_TRANSFER_PREFLIGHT_ONLY': '1'}, capture_output=True, text=True)
(PREP/'CPU_preflight.log').write_text(check.stdout+check.stderr)
check.check_returncode()
command = ['sbatch', '--parsable', '--array=0', '--nice=0', '--export=ALL,'+
           ','.join(k+'='+v for k, v in startup_env.items()), str(launcher)]
job = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
(PREP/'startup_submission.json').write_text(json.dumps({'job': job, 'command': command,
    'environment': startup_env, 'manifest': pin(manifest), 'launcher': pin(launcher),
    'CPU_preflight': 'pass', 'actual_physical_startup': 'pending', 'confirmation': False}, indent=2)+'\n')
print(json.dumps({'startup_job': job, 'source': str(SOURCE), 'manifest': pin(manifest)}), flush=True)
