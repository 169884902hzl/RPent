"""Prepare a bounded stop-enabled follow-up on the same visited original state."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--parent-preparation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-output', type=Path, required=True)
    args = parser.parse_args()
    if not all(path.is_absolute() for path in (args.source, args.parent_preparation, args.output, args.run_output)):
        raise ValueError('absolute paths required')
    parent = json.loads((args.parent_preparation / 'preparation.json').read_text())
    identity_path = Path(parent['source_identity']['path'])
    if ref(identity_path) != parent['source_identity'] or str(args.source) != parent['source']:
        raise ValueError('reuse the original immutable source identity')
    base_plan = Path(parent['manifest']['path'])
    if ref(base_plan) != parent['manifest']:
        raise ValueError('parent manifest changed')
    spec = importlib.util.spec_from_file_location('immutable_prepare_smoke',
        args.source / 'coordination/microwave_runtime_wiring_20261007/prepare_smoke.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.output.mkdir(parents=True, exist_ok=False)
    plan_path = args.output / 'stop_identity48.json'
    module.prepare(base_plan, plan_path, enable_stop=True, max_chunks=48, source_identity_file=identity_path)
    plan = json.loads(plan_path.read_text())
    if plan['cases'][0]['episode'] != {'suite': 'libero_90', 'task': 33, 'seed': 0}:
        raise ValueError('only the previously visited original task33/init0')
    plan['source_snapshot_sha256'] = hashlib.sha256(json.dumps(plan['source_snapshot'], sort_keys=True).encode()).hexdigest()
    plan.update(purpose='visited original stop-enabled 48-block development smoke; no qualification',
                train_allowed=False, training_allowed=False, qualification_authorized=False,
                comparison_baseline_job=4577, thresholds_changed=False,
                policy_action_prefix_paired=False)
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    receipt = {'source_identity': ref(identity_path), 'manifest': ref(plan_path),
        'source': str(args.source), 'commit': plan['source_snapshot']['commit'],
        'launcher': plan['launcher'], 'run_output': str(args.run_output),
        'GPU_requested': 1, 'node_binding': None, 'GPU_submitted': False,
        'qualification': False, 'new_training_rows': 0, 'thresholds_changed': False}
    (args.output / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
