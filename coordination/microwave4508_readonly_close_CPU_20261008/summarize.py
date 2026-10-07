"""Summarize only explicit microwave readonly records and post-execution labels."""

from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path


def identity(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    path = root / 'records.json.gz'
    data = json.loads(gzip.decompress(path.read_bytes()))
    helper = root.parent / 'microwave4507_continuous_close_CPU_20261008/summarize.py'
    spec = importlib.util.spec_from_file_location('continuous_microwave_summary', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = module.summary(data)
    labels = defaultdict(list)
    for score in data['private_scores']:
        block = score['chunk'] + (score['phase'] == 'after_actual_chunk')
        labels[block].append(score)
    public, frames = [], []
    for record in data['public_records']:
        phase, block = record['phase'], record.get('chunks')
        measurement = record['measurement']
        withdrawal = record['frames'][0].get('withdrawal') or {}
        callback_label = next((score['label'] for score in reversed(labels[block])
                               if score['phase'] == 'after_public_stop_before_recovery'), None)
        action_label = next((score['label'] for score in labels[block] if score['phase'] == 'after_actual_chunk'), None)
        row = {'phase': phase, 'block': block, 'status': measurement.get('status'), 'reason': measurement.get('reason'),
            'endpoint_candidate': measurement.get('endpoint_candidate'), 'endpoint_reached': measurement.get('endpoint_reached'),
            'stop_admitted': measurement.get('stop_admitted'), 'intervening_controls': record.get('intervening_controls'),
            'withdrawal_released': 'release' in withdrawal, 'withdrawal_moves': len(withdrawal.get('moves', [])),
            'physical_interval_controls': sum(frame.get('interval_controls', 0) for frame in record['frames']),
            'action_end_private': action_label, 'after_callback_private': callback_label}
        row['false_stop'] = measurement.get('stop_admitted') is True and callback_label is not None and callback_label.get('satisfied') is False
        row['endpoint_lost_after_callback'] = (action_label is not None and action_label.get('satisfied') is True
                                                and callback_label is not None and callback_label.get('satisfied') is False)
        public.append(row)
        for frame in record['frames']:
            frames.append({'phase': phase, 'block': block, 'source_step': frame['source_step'],
                'source_cameras': frame['source_cameras'], 'fixed_available': bool(frame.get('frame')),
                'door_available': bool(frame.get('moving')), 'occluded': frame.get('occluded'),
                'withdrawal_reason': (frame.get('withdrawal') or {}).get('reason')})
    checks = {'routine_probes_without_controls': all(row['intervening_controls'] == 0 and not row['withdrawal_released']
                    and row['withdrawal_moves'] == 0 and row['physical_interval_controls'] == 0 for row in public if row['phase'] == 'probe'),
        'confirmations_preceded_by_candidate': all(any(prior['phase'] == 'probe' and prior['block'] == row['block']
                    and prior['endpoint_candidate'] is True for prior in public[:i]) for i, row in enumerate(public) if row['phase'] == 'after')}
    summary = {'phase_counts': dict(Counter(row['phase'] for row in public)), 'public_frames': len(frames),
        'both_planes_frames': sum(row['fixed_available'] and row['door_available'] for row in frames),
        'source_camera_counts': dict(Counter(camera for frame in frames for camera in frame['source_cameras'])),
        'occlusion_counts': dict(Counter(str(frame['occluded']) for frame in frames)),
        'probe_candidates': sum(row['endpoint_candidate'] is True for row in public),
        'admitted_stops': sum(row['stop_admitted'] is True for row in public),
        'false_stops_with_private_label': sum(row['false_stop'] for row in public),
        'endpoint_lost_after_callback_blocks': len({row['block'] for row in public if row['endpoint_lost_after_callback']}),
        'withdrawal_release_calls': sum(row['withdrawal_released'] for row in public),
        'withdrawal_move_calls': sum(row['withdrawal_moves'] for row in public),
        'interval_controls': sum(row['physical_interval_controls'] for row in public), 'checks': checks}
    if not all(checks.values()):
        raise ValueError('readonly physical callback contract failed: ' + json.dumps(checks))
    result = {'version': 'microwave4508-readonly-close-diagnosis/1-dev', 'physical': base, 'summary': summary,
        'public_records': public, 'frames': frames, 'remote_inputs': data['inputs'],
        'interpretation': 'Single visited-original development state. Private joint scores are post-execution labels, never controls. A provisional endpoint is not an admitted stop. No independent-trial qualification claim.',
        'training_allowed': False, 'qualification': False}
    output = root / 'diagnosis.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2) + '\n')
    (root / 'manifest.json').write_text(json.dumps({'files': [identity(p) for p in (path, output, Path(__file__), root / 'collect.py', helper)],
        'training_allowed': False, 'qualification': False, 'remote_inputs': data['inputs']}, indent=2) + '\n')
    print(json.dumps({'job': data['job'], 'summary': summary, 'private_after': data['private_after']}))
