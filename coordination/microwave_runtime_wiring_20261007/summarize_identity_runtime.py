"""Summarize the explicit public capture ledger without reading private labels."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def summarize(plan_path, ledger_path, output, job):
    plan = json.loads(plan_path.read_text())
    rows = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    if len(rows) != 1 or rows[0]['case']['name'] != plan['cases'][0]['name']:
        raise ValueError('one explicit matching original smoke required')
    first = rows[0].get('first_attempt') or {}
    temporal = (first.get('verification_measurements') or {}).get('microwave_temporal', [])
    samples = []
    for record in temporal:
        for sample in record['frames']:
            views = sample.get('views') or {}
            samples.append({'phase': record['phase'], 'chunks': record.get('chunks'),
                'source_step': sample['source_step'], 'source_cameras': sample.get('source_cameras'),
                'frame_present': sample.get('frame') is not None, 'moving_present': sample.get('moving') is not None,
                'candidate': record.get('measurement') or {},
                'views': {camera: {'frame_present': views.get(camera, {}).get('frame') is not None,
                    'moving_present': views.get(camera, {}).get('moving') is not None,
                    'moving': views.get(camera, {}).get('moving'),
                    'tracking': views.get(camera, {}).get('identity_tracking'),
                    'robot_mask': (sample.get('robot_mask_evidence') or {}).get(camera),
                    'measurement_counts': views.get(camera, {}).get('measurement_counts')}
                    for camera in ('agentview', 'wrist')},
                'arm_withdrawn': sample.get('arm_withdrawn'), 'occluded': sample.get('occluded'),
                'artifacts': sample.get('artifacts')})
    probe = [sample for sample in samples if sample['phase'] == 'probe']
    cameras = {}
    for camera in ('agentview', 'wrist'):
        views = [sample['views'][camera] for sample in probe]
        cameras[camera] = {'probe_frames': len(views),
            'frame_present': sum(view['frame_present'] for view in views),
            'moving_present': sum(view['moving_present'] for view in views),
            'tracked_current_cloud_present': sum(bool((view['moving'] or {}).get('identity_tracking_version')) for view in views),
            'tracking_attempts': sum(view['tracking'] is not None for view in views),
            'tracking_reasons': dict(Counter((view['tracking'] or {}).get('reason') for view in views if view['tracking'])),
            'tracking_errors': dict(Counter((view['tracking'] or {}).get('error') for view in views
                                            if (view['tracking'] or {}).get('error')))}
    result = {'job': job, 'manifest': ref(plan_path), 'ledger': ref(ledger_path),
        'private_labels_read': False, 'public_monitor_controls': 0, 'qualification': False,
        'source_snapshot': {'path': plan['source_snapshot']['path'], 'commit': plan['source_snapshot']['commit'],
                            'archive': plan['source_snapshot']['archive']},
        'status': rows[0]['status'], 'infrastructure_failure': rows[0].get('infrastructure_failure'),
        'wall_s': rows[0]['wall_s'], 'physically_executed': first.get('physically_executed'),
        'server_chunk_execution': {key: value for key, value in (rows[0].get('server_chunk_execution') or {}).items()
                                   if key != 'raw_native_success_controls'},
        'public_receipt': first.get('receipt'), 'temporal_records': len(temporal),
        'public_frames': len(samples), 'camera_summary': cameras,
        'candidate_reasons': dict(Counter(sample['candidate'].get('reason') for sample in probe)),
        'endpoint_candidates': sum(sample['candidate'].get('endpoint_candidate') is True for sample in probe),
        'temporal_stop_count': sum(record.get('measurement', {}).get('stop_admitted') is True for record in temporal),
        'samples': samples}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'samples'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--job', type=int, required=True)
    args = parser.parse_args()
    summarize(args.manifest, args.ledger, args.output, args.job)
