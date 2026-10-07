"""Recompute actual wrist fixed-plane support in job4500's eighteen frames."""

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
LEDGER = ROOT / 'results/harness_v5/microwave_observation_pose_original_20261008/capture8/episodes.jsonl'
MODULE = ROOT / 'coordination/microwave_wrist_roi_CPU_20261008/v5_microwave_wrist_roi.py'
OUTPUT = ROOT / 'results/harness_v5/microwave_wrist_roi_CPU_20261008/recompute18'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load(record):
    path = Path(record['path'])
    if ref(path)['sha256'] != record['sha256']:
        raise ValueError('explicit public artifact changed: ' + str(path))
    with np.load(path, allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError('one explicit saved array required')
        return saved[saved.files[0]]


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('wrist_roi_overlay', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lines = LEDGER.read_text().splitlines()
    if len(lines) != 1:
        raise ValueError('one explicit job4500 episode required')
    row = json.loads(lines[0])
    if row['case']['episode'] != {'suite': 'libero_90', 'task': 33, 'seed': 0}:
        raise ValueError('registered visited original state differs')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    records = []
    inputs = [ref(LEDGER), ref(MODULE)]
    original_verdicts = []
    for temporal in row['first_attempt']['verification_measurements']['microwave_temporal']:
        original_verdicts.append(temporal['measurement'])
        for frame in temporal['frames']:
            reference = frame['views']['agentview']['frame']
            fixed = load(reference)
            wrist = load(frame['artifacts']['wrist']['world'])
            inputs.extend([ref(Path(reference['path'])), frame['artifacts']['wrist']['world']])
            fit, evidence, cloud, mask = module.fit_wrist_fixed_roi(wrist, reference, fixed, source_step=frame['source_step'])
            if fit is not None:
                cloud_path = OUTPUT / f"step{frame['source_step']}_wrist_fixed.npz"
                np.savez_compressed(cloud_path, array=cloud)
                mask_path = OUTPUT / f"step{frame['source_step']}_wrist_fixed_mask.npz"
                np.savez_compressed(mask_path, array=mask)
                evidence.update(cloud=ref(cloud_path), mask=ref(mask_path))
            records.append({'step': frame['source_step'], 'phase': temporal['phase'], 'block': temporal.get('chunks'),
                'original_wrist_fixed_available': bool(frame['views']['wrist'].get('frame')),
                'original_wrist_moving_available': bool(frame['views']['wrist'].get('moving')),
                'new_wrist_fixed_available': fit is not None, 'roi_evidence': evidence,
                'wrist_robot_occlusion': frame['robot_mask_evidence'].get('wrist'),
                'complete_runtime_occlusion_remeasurement_required': True})
    result = {'version': 'microwave4500-wrist-roi-recompute18/1-dev', 'job': 4500,
        'summary': {'frames': len(records), 'old_wrist_fixed': sum(r['original_wrist_fixed_available'] for r in records),
                    'new_wrist_fixed': sum(r['new_wrist_fixed_available'] for r in records),
                    'old_wrist_moving': sum(r['original_wrist_moving_available'] for r in records),
                    'complete_new_public_verdicts': 0, 'original_verdicts_changed': 0},
        'records': records, 'original_verdicts_retained': original_verdicts,
        'interpretation': 'CPU geometric support only. Original wrist masks were not saved with usable fixed-plane occlusion evidence, so no new temporal stop or fusion verdict is manufactured. Real runtime must remeasure wrist door/robot masks. Existing verdicts are retained.',
        'inputs': inputs, 'private_labels_read': False, 'qualification': False, 'training_allowed': False}
    path = OUTPUT / 'report.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'report': ref(path), 'summary': result['summary']}))
