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
    baseline_path = root.parent / 'microwave4497_close_temporal_CPU_20261008/records.json'
    baseline = json.loads(baseline_path.read_text())
    continuous_path = root.parent / 'microwave4507_continuous_close_CPU_20261008/records.json.gz'
    compared = [(baseline_path, baseline), (path, data)]
    if continuous_path.is_file():
        compared.insert(1, (continuous_path, json.loads(gzip.decompress(continuous_path.read_bytes()))))
    wrist_path = root.parent / 'microwave4516_wrist_roi_close_CPU_20261008/records.json.gz'
    if wrist_path.is_file():
        compared.insert(-1, (wrist_path, json.loads(gzip.decompress(wrist_path.read_bytes()))))
    readonly_path = root.parent / 'microwave4508_readonly_close_CPU_20261008/records.json.gz'
    if readonly_path.is_file():
        compared.insert(-1, (readonly_path, json.loads(gzip.decompress(readonly_path.read_bytes()))))
    prefixes = []
    first = module.summary(baseline)['first_contact_block']
    for input_path, observed in compared:
        for key in ('episode', 'state_sha256', 'official_init_index', 'mode', 'subtask_prompt'):
            if observed['case'][key] != data['case'][key]:
                raise ValueError('paired state/contact field differs: ' + key)
        prefix = module.summary(observed)['first_contact_block']
        prefixes.append({'job': observed['job'], **prefix, 'input': identity(input_path),
            'equal_first_action_to4497': prefix['first_action'] == first['first_action'],
            'equal_first_block_to4497': prefix['actions_sha256'] == first['actions_sha256'],
            'maximum_first_block_action_difference_to4497': max(abs(x - y) for row_a, row_b in zip(first['actions'], prefix['actions'])
                                                                for x, y in zip(row_a, row_b))})
    labels = defaultdict(list)
    for score in data['private_scores']:
        block = score['chunk'] + (score['phase'] == 'after_actual_chunk')
        labels[block].append(score)
    public, frames, roi_records = [], [], []
    for record in data['public_records']:
        phase, block = record['phase'], record.get('chunks')
        measurement = record['measurement']
        withdrawal = record['frames'][0].get('withdrawal') or {}
        callback_label = next((score['label'] for score in reversed(labels[block])
                               if score['phase'] == 'after_public_stop_before_recovery'), None)
        action_label = next((score['label'] for score in labels[block] if score['phase'] == 'after_actual_chunk'), None)
        row = {'phase': phase, 'block': block, 'status': measurement.get('status'), 'reason': measurement.get('reason'),
            'endpoint_candidate': measurement.get('endpoint_candidate'), 'staged_confirmation': measurement.get('staged_confirmation'), 'endpoint_reached': measurement.get('endpoint_reached'),
            'stop_admitted': measurement.get('stop_admitted'), 'intervening_controls': record.get('intervening_controls'),
            'withdrawal_released': 'release' in withdrawal, 'withdrawal_moves': len(withdrawal.get('moves', [])),
            'physical_interval_controls': sum(frame.get('interval_controls', 0) for frame in record['frames']),
            'action_end_private': action_label, 'after_callback_private': callback_label}
        row['false_stop'] = measurement.get('stop_admitted') is True and callback_label is not None and callback_label.get('satisfied') is False
        row['endpoint_lost_after_callback'] = (action_label is not None and action_label.get('satisfied') is True
                                                and callback_label is not None and callback_label.get('satisfied') is False)
        public.append(row)
        for frame in record['frames']:
            wrist = frame['views'].get('wrist', {})
            roi = wrist.get('fixed_roi_guidance')
            if roi:
                roi_records.append({'block': block, 'phase': phase, 'source_step': frame['source_step'],
                    'status': roi['status'], 'reason': roi['reason'], 'wrist_points': roi['wrist_points'],
                    'fusion_promoted': roi.get('fusion_promoted'),
                    'wrist_fixed_available': bool(wrist.get('frame')), 'wrist_door_available': bool(wrist.get('moving')),
                    'wrist_occlusion': frame['robot_mask_evidence'].get('wrist'),
                    'residual_m': (roi.get('measured_plane') or {}).get('residual_p90_m'),
                    'reference_angle_difference_deg': roi.get('reference_angle_difference_deg'),
                    'reference_normal_drift_m': roi.get('reference_normal_drift_m')})
            frames.append({'phase': phase, 'block': block, 'source_step': frame['source_step'],
                'source_cameras': frame['source_cameras'], 'fixed_available': bool(frame.get('frame')),
                'door_available': bool(frame.get('moving')), 'occluded': frame.get('occluded'),
                'withdrawal_reason': (frame.get('withdrawal') or {}).get('reason'),
                'wrist_fixed_available': bool(wrist.get('frame')), 'wrist_door_available': bool(wrist.get('moving')),
                'wrist_occluded': (frame['robot_mask_evidence'].get('wrist') or {}).get('occluded')})
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
    summary.update(staged_reasons=dict(Counter((row.get('staged_confirmation') or {}).get('reason', 'not_staged') for row in public)),
        staged_withdrawals=sum((row.get('staged_confirmation') or {}).get('withdrawal_admitted') is True for row in public),
        roi_frames=len(roi_records), roi_measured=sum(row['status'] == 'measured' for row in roi_records),
        roi_promoted=sum(row['fusion_promoted'] is True for row in roi_records),
        roi_reason_counts=dict(Counter(row['reason'] for row in roi_records)),
        wrist_two_planes=sum(row['wrist_fixed_available'] and row['wrist_door_available'] for row in frames),
        wrist_complete_unobstructed_two_planes=sum(row['wrist_fixed_available'] and row['wrist_door_available']
                                                    and row['wrist_occluded'] is False for row in frames))
    if not all(checks.values()):
        raise ValueError('readonly physical callback contract failed: ' + json.dumps(checks))
    result = {'version': 'microwave4523-staged-candidate-close-diagnosis/1-dev', 'physical': base, 'summary': summary,
        'first_contact_prefixes': prefixes,
        'prefix_interpretation': 'Policy input tensors/noise were not hashed; differing physical prefixes prohibit attribution to a single callback change.',
        'public_records': public, 'frames': frames, 'roi_records': roi_records, 'remote_inputs': data['inputs'],
        'interpretation': 'Single visited-original development state. Private joint scores are post-execution labels, never controls. A provisional endpoint is not an admitted stop. No independent-trial qualification claim.',
        'training_allowed': False, 'qualification': False}
    output = root / 'diagnosis.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2) + '\n')
    (root / 'manifest.json').write_text(json.dumps({'files': [identity(p) for p in (path, output, Path(__file__), root / 'collect.py', helper)],
        'comparison_inputs': [identity(p) for p, _ in compared],
        'training_allowed': False, 'qualification': False, 'remote_inputs': data['inputs']}, indent=2) + '\n')
    print(json.dumps({'job': data['job'], 'summary': summary, 'private_after': data['private_after']}))
