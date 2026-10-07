"""Pair the explicit job4497 and4507 ledgers by state, source and contact block."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def summary(data):
    action_end = [score for score in data['private_scores'] if score['phase'] == 'after_actual_chunk']
    values = [{'block': score['chunk'] + 1, 'satisfied': score['label'].get('satisfied'),
               'joint_qpos': score['label'].get('joint_qpos'), 'sim_time': score['label'].get('sim_time')}
              for score in action_end]
    return {'job': data['job'], 'status': data['status'], 'wall_s': data['wall_s'],
            'server_chunk_execution': data['server_chunk_execution'], 'receipt': data['receipt'],
            'public_temporal_records': len(data['public_records']),
            'private_label_counts': dict(Counter(score['phase'] for score in data['private_scores'])),
            'action_end_true': sum(v['satisfied'] is True for v in values),
            'action_end_count': len(values), 'action_end_labels': values,
            'private_before': data['private_before'], 'private_after': data['private_after'],
            'contract': data['contract']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    current_path = root / 'records.json.gz'
    baseline_path = root.parent / 'microwave4497_close_temporal_CPU_20261008/records.json'
    baseline, current = json.loads(baseline_path.read_text()), json.loads(gzip.decompress(current_path.read_bytes()))
    for key in ('episode', 'state_sha256', 'official_init_index', 'mode', 'subtask_prompt'):
        if baseline['case'][key] != current['case'][key]:
            raise ValueError('paired state/contact field differs: ' + key)
    if baseline['source_snapshot'] != current['source_snapshot']:
        raise ValueError('paired immutable source differs')
    before, after = summary(baseline), summary(current)
    if before['action_end_count'] != 40 or after['action_end_count'] != 40:
        raise ValueError('paired forty-block contact budget did not execute')
    result = {'version': 'microwave4507-continuous-close-pair/1-dev', 'baseline': before, 'continuous': after,
        'matching_case_fields': ['episode', 'state_sha256', 'official_init_index', 'mode', 'subtask_prompt'],
        'matching_source_snapshot': current['source_snapshot'], 'training_allowed': False, 'qualification': False,
        'interpretation': 'One visited original state, paired development comparison. Private labels are post-execution scores only. No claims of independent trial counts or skill qualification.',
        'inputs': [ref(baseline_path), ref(current_path)], 'remote_inputs': current['inputs']}
    path = root / 'diagnosis.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, indent=2) + '\n')
    (root / 'manifest.json').write_text(json.dumps({'files': [ref(p) for p in (current_path, path, Path(__file__), root / 'collect.py')],
        'qualification': False, 'training_allowed': False, 'remote_inputs': current['inputs']}, indent=2) + '\n')
    print(json.dumps({name: {key: row[key] for key in ('job', 'wall_s', 'action_end_true', 'action_end_count', 'private_after', 'public_temporal_records')}
                      for name, row in (('baseline', before), ('continuous', after))}))
