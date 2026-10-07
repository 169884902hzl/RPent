"""Pair job4497 with continuous pi0.5, using the same source and visited state."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/microwave584_source_CPU_20261008/r1/close_stop40.json'
BASE_SHA = '5526843d9e229695611fbeb34e0d7b7f0d135b825bb7240a36744670224901a5'
OUT = ROOT / 'results/harness_v5/microwave_no_callback40_CPU_20261008/r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    if ref(BASE)['sha256'] != BASE_SHA:
        raise ValueError('registered job4497 plan changed')
    before = json.loads(BASE.read_text())
    if (before['cohort'] != 'development' or len(before['cases']) != 1
            or before['cases'][0]['episode'] != {'suite': 'libero_90', 'task': 33, 'seed': 0}):
        raise ValueError('one explicit visited original state required')
    plan = copy.deepcopy(before)
    condition = plan['conditions'][plan['cases'][0]['condition']]
    if (condition['max_chunks'] != 40 or condition['overrides']['microwave_temporal_capture_v1'] is not True
            or condition['overrides']['microwave_temporal_stop_v1'] is not True):
        raise ValueError('retain job4497 budget and verify its original flags')
    condition['overrides']['microwave_temporal_capture_v1'] = False
    condition['overrides']['microwave_temporal_stop_v1'] = False
    plan['producer'] = ref(Path(__file__).resolve())
    plan.update(purpose='continuous pi0.5 same-source40 paired development comparison to4497; not qualification',
        comparison_baseline={'job': 4497, 'manifest': ref(BASE)},
        comparison_changes={'microwave_temporal_capture_v1': {'before': True, 'after': False},
                            'microwave_temporal_stop_v1': {'before': True, 'after': False}},
        qualification_authorized=False, new_training_rows=0)
    plan['cases'][0]['name'] += '_continuous_no_callback_dev'
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / 'close_no_callback40.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    receipt = {'manifest': ref(path), 'source_snapshot': plan['source_snapshot']['path'],
        'source_archive': plan['source_snapshot']['archive'], 'launcher': plan['launcher'],
        'changes': plan['comparison_changes'], 'producer': plan['producer'],
        'output': str(ROOT / 'results/harness_v5/microwave_no_callback40_original_20261008/close40'),
        'GPU_submitted': False, 'qualification': False}
    (OUT / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    build()
