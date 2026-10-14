"""Pin tangent entry with identity tracking and the corrected public verifier."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_tracking_20261009_r4'
SOURCE = ROOT / 'source_v5_analytic_tangent_tracking_20261009_r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent snapshot changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['robots/libero/v5_analytic_grasp.py',
               'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py']
    for name in changed:
        shutil.copy2(ROOT / name, SOURCE / name)
    for name in ('robots/libero/v5_runtime.py', 'harness_v5_eval.py'):
        path = SOURCE / name
        original = path.read_text()
        if name.endswith('v5_runtime.py'):
            updates = [('        analytic_grasp_v1: bool = False,',
                        '        analytic_grasp_v1: bool = False,\n        analytic_side_route_v1: bool = False,'),
                       ('        self.analytic_grasp_v1 = analytic_grasp_v1',
                        '        self.analytic_grasp_v1 = analytic_grasp_v1\n        self.analytic_side_route_v1 = analytic_side_route_v1')]
        else:
            updates = [('"analytic_grasp_v1", "grasp_rim_v1"',
                        '"analytic_grasp_v1", "analytic_side_route_v1", "grasp_rim_v1"'),
                       ('    parser.add_argument("--analytic-grasp-v1", action="store_true")',
                        '    parser.add_argument("--analytic-grasp-v1", action="store_true")\n    parser.add_argument("--analytic-side-route-v1", action="store_true")')]
        for before, after in updates:
            if original.count(before) != 1:
                raise ValueError(f'flag location is not unique in {name}')
            original = original.replace(before, after)
        path.write_text(original)
        changed.append(name)
    with tarfile.open(parent['archive']['path']) as archive:
        members = list(dict.fromkeys([*archive.getnames(), *changed]))
    archive_path = Path(str(SOURCE) + '.tar')
    with tarfile.open(archive_path, 'x') as archive:
        for name in members:
            archive.add(SOURCE / name, arcname=name, recursive=False)
    names = list(dict.fromkeys([*[row['relative_path'] for row in parent['files']], *changed]))
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(archive_path),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in names],
        'purpose': 'public tangent-axis side entry; tracked identity and calibrated empty aperture; Pi0.5 and servo tolerances unchanged'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    cpu = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py', '-q'],
        cwd=SOURCE, env={**os.environ, 'PYTHONPATH': str(SOURCE)}, capture_output=True, text=True)
    (SOURCE / 'tangent_source_tests.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    print(json.dumps({'snapshot': ref(SOURCE / 'source_snapshot.json'),
                      'archive': snapshot['archive'], 'CPU_tests': cpu.stdout.strip()}))


if __name__ == '__main__':
    main()
