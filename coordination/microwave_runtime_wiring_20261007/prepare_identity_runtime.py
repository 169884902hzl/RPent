"""Build an immutable runtime smoke from an explicit registered source index."""

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/microwave_front_hint_CPU_20261008/r1'
BASE_IDENTITY = {'path': str(BASE / 'source_identity.json'),
                 'sha256': '33613a51662cddad39d1964c9ad1bc3689951e2c8ae3c7c8cd50e042b46166e4'}
BASE_PLAN = {'path': str(BASE / 'close_front_hint40.json'),
             'sha256': '9490111c7e3d8930f92ad44e2d84174ad393a182ccdbd73e931919a40f536ef9'}
PREPARE = 'coordination/microwave_runtime_wiring_20261007/prepare_smoke.py'
LAUNCHER = 'coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch'
RECIPE = 'coordination/microwave_runtime_wiring_20261007/prepare_identity_runtime.py'


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record['path'])
    if not path.is_absolute() or ref(path)['sha256'] != record['sha256']:
        raise ValueError('registered source/input changed: ' + str(path))
    return path


def pack(repo, output):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])
    commit = git('rev-parse', 'HEAD').decode().strip()
    modules = git('ls-files', 'robots/libero').decode().splitlines()
    names = sorted(set([name for name in modules if name.endswith('.py')] + [
        PREPARE, LAUNCHER, RECIPE, 'harness_v5_eval.py', 'typed_choice_eval.py',
        'scripts/probe_v5_microwave_public571.py', 'scripts/probe_v5_skill501_original.py',
        'scripts/v5_probe_preflight.py']))
    overlays = []
    for name in names:
        raw = git('show', commit + ':' + name)
        overlays.append({'relative_path': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                         'data_base64': base64.b64encode(raw).decode()})
    output.write_text(json.dumps({'commit': commit, 'base_identity': BASE_IDENTITY,
                                 'base_plan': BASE_PLAN, 'overlays': overlays}, indent=2) + '\n')
    print(json.dumps({'packet': ref(output), 'commit': commit, 'overlays': len(overlays)}))


def build(packet_path, snapshot, output):
    packet = json.loads(packet_path.read_text())
    if packet['base_identity'] != BASE_IDENTITY or packet['base_plan'] != BASE_PLAN:
        raise ValueError('unexpected original-task runtime-smoke source')
    base = json.loads(checked(BASE_IDENTITY).read_text())
    checked(base['archive'])
    checked(BASE_PLAN)
    snapshot.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for record in base['files']:
        old = checked(record)
        name = record['relative_path']
        if old != Path(base['path']) / name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('source outside explicit index')
        destination = snapshot / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, destination)
        files[name] = destination
    changes = []
    for overlay in packet['overlays']:
        name = overlay['relative_path']
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('invalid overlay path')
        raw = base64.b64decode(overlay['data_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != overlay['sha256']:
            raise ValueError('overlay hash differs')
        destination = snapshot / name
        before = ref(destination)['sha256'] if destination.exists() else None
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        files[name] = destination
        if before != overlay['sha256']:
            changes.append({'relative_path': name, 'before_sha256': before, 'sha256': overlay['sha256']})
    indexed = {name: {**ref(path), 'relative_path': name} for name, path in sorted(files.items())}
    archive = Path(str(snapshot) + '.tar')
    with tarfile.open(archive, 'x') as stream:
        for name, record in indexed.items():
            stream.add(record['path'], arcname=name, recursive=False)
    identity = {'path': str(snapshot), 'commit': packet['commit'], 'files': list(indexed.values()),
                'archive': ref(archive), 'base_source_identity': BASE_IDENTITY, 'overlays': changes}
    identity_path = output / 'source_identity.json'
    identity_path.write_text(json.dumps(identity, indent=2) + '\n')
    spec = importlib.util.spec_from_file_location('prepare_microwave_identity_smoke', snapshot / PREPARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan_path = output / 'capture_identity40.json'
    module.prepare(Path(BASE_PLAN['path']), plan_path, max_chunks=40, source_identity_file=identity_path)
    plan = json.loads(plan_path.read_text())
    plan.update(training_allowed=False, train_allowed=False, qualification_authorized=False,
                purpose='one visited original task33/init0 runtime identity capture-only smoke; not qualification')
    plan['cases'][0].update(previously_used_for_selection=True, excluded_from_training=True)
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    receipt = {'source_identity': ref(identity_path), 'manifest': ref(plan_path),
               'source': str(snapshot), 'commit': packet['commit'], 'launcher': indexed[LAUNCHER],
               'source_files': len(indexed), 'changed_files': changes, 'GPU_submitted': False,
               'cohort': 'development', 'new_training_rows': 0, 'qualification': False}
    (output / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.pack:
        pack(args.pack.resolve(), args.packet.resolve())
    else:
        if not all(path and path.is_absolute() for path in (args.snapshot, args.output, args.packet)):
            raise ValueError('absolute packet/snapshot/output required')
        build(args.packet, args.snapshot, args.output)
