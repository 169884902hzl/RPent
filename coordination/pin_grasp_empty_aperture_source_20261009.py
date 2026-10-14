"""Pin the public verifier correction without changing registered contact paths."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_tracking_20261009_r3'
SOURCE = ROOT / 'source_v5_grasp_public_tracking_20261009_r4'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent snapshot changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['robots/libero/v5_grasp_public_tracking.py',
               'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
               'robots/libero/v5_runtime.py']
    for name in changed[:2]:
        shutil.copy2(ROOT / name, SOURCE / name)
    path = SOURCE / changed[2]
    text = path.read_text()
    old = 'paired = evaluate_tracked_coupling(first, second, time.perf_counter() - started)'
    if text.count(old) != 1:
        raise ValueError('parent public verifier call not identified')
    path.write_text(text.replace(old, old[:-1] + ',\n'
        "                opening_calibration=self.grasp_measurement_calibration['opening_calibration']\n"
        '                if self.grasp_measurement_calibration else None)'))
    with tarfile.open(parent['archive']['path']) as archive:
        names = list(dict.fromkeys([*archive.getnames(), *changed]))
    archive_path = Path(str(SOURCE) + '.tar')
    with tarfile.open(archive_path, 'x') as archive:
        for name in names:
            archive.add(SOURCE / name, arcname=name, recursive=False)
    names = list(dict.fromkeys([*[r['relative_path'] for r in parent['files']], *changed]))
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(archive_path),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in names],
        'purpose': 'tracked public verifier rejects original-calibrated empty aperture even with missing RGB-D; contact paths unchanged'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    result = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py', '-q'], cwd=SOURCE,
        env={**os.environ, 'PYTHONPATH': str(SOURCE)}, capture_output=True, text=True)
    (SOURCE / 'public_empty_aperture_tests.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    print(json.dumps({'snapshot': ref(SOURCE / 'source_snapshot.json'),
                      'archive': snapshot['archive'], 'CPU_tests': result.stdout.strip()}))


if __name__ == '__main__':
    main()
