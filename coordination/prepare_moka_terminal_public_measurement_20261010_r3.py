"""Prepare a same-pool read-only terminal measurement regression."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_moka_native_callbacks_20261010_r2'
SOURCE = ROOT / 'source_v5_moka_terminal_public_measurement_20261010_r3'
OLD = ROOT / 'results/harness_v5/moka_native_callbacks_selection100_20261010_r2/preparation'
PREP = ROOT / 'results/harness_v5/moka_terminal_public_measurement_selection100_20261010_r3/preparation'
STAGING = ROOT / 'coordination/moka_terminal_public_measurement_r3_staging'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    body = (PARENT / 'robots/libero/v5_runtime.py').read_text()
    body = body.replace('        placement_endpoint_stop_v1: bool = False,\n',
        '        placement_endpoint_stop_v1: bool = False,\n        subtask_terminal_measurement_v1: bool = False,\n')
    body = body.replace('        self.placement_endpoint_stop_v1 = bool(placement_endpoint_stop_v1)\n',
        '        self.placement_endpoint_stop_v1 = bool(placement_endpoint_stop_v1)\n        self.subtask_terminal_measurement_v1 = bool(subtask_terminal_measurement_v1)\n')
    start = body.index('        if self.p.env.terminated or self.p.env.truncated:', body.index('    def execute_subtask('))
    end = body.index('        if (getattr(self, "stove_contact_unload_v1", False)', start)
    current = (STAGING / 'v5_runtime.py').read_text()
    begin = current.index('        if self.p.env.terminated or self.p.env.truncated:', current.index('    def execute_subtask('))
    finish = current.index('        if (getattr(self, "stove_contact_unload_v1", False)', begin)
    if 'observe_terminal' in body[start:end] or body.count('subtask_terminal_measurement_v1: bool') != 1:
        raise ValueError('unexpected parent constructor or terminal block')
    (SOURCE / 'robots/libero/v5_runtime.py').write_text(body[:start] + current[begin:finish] + body[end:])
    body = (PARENT / 'harness_v5_eval.py').read_text()
    original = '                             placement_endpoint_stop_v1=getattr(args, "placement_endpoint_stop_v1", False),\n'
    if body.count(original) != 1:
        raise ValueError('unexpected evaluator forwarding')
    body = body.replace(original, original + '                             subtask_terminal_measurement_v1=getattr(args, "subtask_terminal_measurement_v1", False),\n')
    marker = '    parser.add_argument("--grasp-measurement-calibration", type=Path)'
    if body.count(marker) != 1:
        raise ValueError('unexpected parser layout')
    body = body.replace(marker, '    parser.add_argument("--subtask-terminal-measurement-v1", action="store_true")\n' + marker)
    (SOURCE / 'harness_v5_eval.py').write_text(body)
    for relative in ('robots/libero/v5_placement_endpoint_stop.py',
                     'tests/unit_tests/robots/libero/test_v5_placement_endpoint_stop.py'):
        shutil.copyfile(STAGING / Path(relative).name, SOURCE / relative)
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_placement_endpoint_stop.py',
        'tests/unit_tests/robots/libero/test_v5_subtask_release_reverify.py'], cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    (SOURCE / 'CPU_terminal_public_measurement_r3.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    PREP.mkdir(parents=True, exist_ok=False)
    for name in ('probe_v5_moka_layout24_20261008.py', 'serve_v5_moka_layout24_20261008.py', 'typed_choice_eval.py', 'preflight.py'):
        shutil.copyfile(OLD / name, PREP / name)
    launcher = PREP / 'run_selection100.sbatch'
    launcher.write_text((OLD / launcher.name).read_text().replace(str(OLD.parent), str(PREP.parent)))
    identity = json.loads((OLD / 'source_identity.json').read_text())
    identity.update(path=str(SOURCE), parent_snapshot=str(PARENT),
        identity_kind='native_terminal_read_only_public_measurement',
        CPU_validation={'command': check.args, 'result': check.stdout},
        no_post_terminal_controls=True, native_success_is_not_public_placement_label=True)
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    known = {record['relative_path'] for record in identity['files']}
    for relative in ('robots/libero/v5_placement_endpoint_stop.py',
                     'tests/unit_tests/robots/libero/test_v5_placement_endpoint_stop.py'):
        if relative not in known:
            identity['files'].append({**pin(SOURCE / relative), 'relative_path': relative})
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    identity['archive'] = pin(archive)
    (SOURCE / 'source_identity_terminal_measurement.json').write_text(json.dumps(identity, indent=2) + '\n')
    (PREP / 'source_identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    plan = copy.deepcopy(json.loads((OLD / 'selection100.json').read_text()))
    if len(plan['cases']) != 100 or plan['qualification_authorized'] or plan['training_allowed']:
        raise ValueError('same development selection100 required')
    plan.update(source_path=str(SOURCE), source_snapshot=identity,
        source_identity=pin(PREP / 'source_identity.json'),
        source_snapshot_sha256=hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        producer=pin(Path(__file__)), prior_selection_manifest=pin(OLD / 'selection100.json'),
        comparison_parent=str(OLD.parent), new_confirmation_attempts=0,
        purpose='same original selection100; public terminal measurement with actual preterminal physics and zero added controls')
    for condition in plan['conditions'].values():
        condition['overrides']['subtask_terminal_measurement_v1'] = True
    for record in plan['producer_dependencies']:
        path = Path(record['path'])
        if path.is_relative_to(PARENT):
            record.update(pin(SOURCE / path.relative_to(PARENT)))
        elif path.is_relative_to(OLD):
            record.update(pin(PREP / path.relative_to(OLD)))
    plan['launcher_identity'] = pin(launcher)
    manifest = PREP / 'selection100.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    environment = {**json.loads((OLD / 'startup_submission.json').read_text())['environment'],
        'MOKA_TRANSFER_SOURCE': str(SOURCE), 'MOKA_TRANSFER_MANIFEST': str(manifest),
        'MOKA_TRANSFER_MANIFEST_SHA': pin(manifest)['sha256']}
    check = subprocess.run(['bash', str(launcher)], env={**os.environ, **environment,
        'MOKA_TRANSFER_PREFLIGHT_ONLY': '1'}, cwd='/tmp', capture_output=True, text=True)
    (PREP / 'CPU_preflight.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--array=0', '--nice=0', '--export=ALL,' +
        ','.join(k+'='+v for k,v in environment.items()), str(launcher)], capture_output=True, text=True, check=True)
    receipt = {'job': result.stdout.strip(), 'environment': environment, 'manifest': pin(manifest),
        'launcher': pin(launcher), 'CPU_preflight': 'pass', 'actual_physical_startup': 'pending', 'confirmation': False}
    (PREP / 'startup_submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
