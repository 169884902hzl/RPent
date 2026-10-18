"""Audit saved reference joins, including executed measured-state braking tails."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.bounded_motion import MotionConfig
from rpent.skill_package.trajectory import brake
from scripts.summarize_bounded_probes import distribution


def audit_motion(result):
    trace = result.get('trace', [])
    if not trace or 'reference_acceleration' not in trace[0]:
        return None
    config = MotionConfig(**result['config'])
    metrics = result['metrics']
    report = {'nominal_max_translation_acceleration_jump': metrics.get('reference_max_translation_acceleration_jump'),
        'nominal_max_rotation_acceleration_jump': metrics.get('reference_max_rotation_acceleration_jump'),
        'nominal_max_jerk_limit_ratio': metrics.get('reference_max_jerk_limit_ratio'),
        'stop_reason': result['stop_reason'], 'braking': None}
    braking = result.get('braking')
    if braking is not None:
        report['braking'] = {'executed': braking['executed'], 'reason': braking['reason']}
        if braking['executed']:
            first = next(i for i, sample in enumerate(trace) if sample['braking'])
            previous = trace[first-1]
            initial = braking['initial_derivatives']
            acceleration = np.asarray(initial['acceleration'])
            # This is the actual reference reset from the last commanded
            # nominal state to the measured-state brake, not an adjacent-
            # sample acceleration delta within a continuous polynomial.
            report['braking']['reference_translation_acceleration_jump'] = float(np.linalg.norm(
                acceleration[:3]-np.asarray(previous['reference_acceleration'])[:3]))
            report['braking']['reference_position_jump_m'] = float(np.linalg.norm(
                np.asarray(trace[first]['before']['eef_xyz_m'])-previous['desired']['xyz_m']))
            tails = [brake(np.zeros(3), np.asarray(initial['velocity'])[axes], acceleration[axes],
                jerk=np.asarray(initial['jerk'])[axes], limits=limit) for axes, limit in config.groups()]
            report['braking']['max_jerk_limit_ratio'] = max(segment.maximum(3, slice(None))/limit.jerk
                for tail, (_, limit) in zip(tails, config.groups()) for segment in tail.segments)
            report['braking']['internal_max_translation_acceleration_jump'] = max(
                (float(np.linalg.norm(a.at(a.duration, 2)-b.at(0., 2)))
                 for a, b in zip(tails[0].segments, tails[0].segments[1:])), default=0.)
    return report


def audit_choices(paths):
    motions, joins, sources = [], [], []
    for path in paths:
        raw = path.read_bytes()
        sources.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()})
        previous_motion = None
        for decision_index, line in enumerate(raw.splitlines()):
            row = json.loads(line)
            for detail_index, detail in enumerate(row.get('execution_details', [])):
                result = detail.get('execution', {})
                report = audit_motion(result)
                if report is None:
                    if result.get('steps_used', 0) or result.get('trace'):
                        previous_motion = None
                    continue
                motions.append({'record': str(path), 'decision_index': decision_index,
                    'detail_index': detail_index, **report})
                trace = result['trace']
                if previous_motion is not None:
                    last = previous_motion['trace'][-1]
                    first = trace[0]
                    if last['after'] == first['before']:
                        initial = result.get('initial_derivatives')
                        acceleration = np.asarray(initial[1] if initial is not None else np.zeros(6))
                        joins.append({'record': str(path), 'decision_index': decision_index,
                            'detail_index': detail_index, 'kind': 'adjacent_motion_same_measured_state',
                            'reference_translation_acceleration_jump': float(np.linalg.norm(
                                acceleration[:3]-np.asarray(last['reference_acceleration'])[:3])),
                            'reference_position_jump_m': float(np.linalg.norm(
                                np.asarray(first['before']['eef_xyz_m'])-last['desired']['xyz_m']))})
                previous_motion = result
    brake_joins = [r['braking'] for r in motions if r['braking'] and r['braking']['executed']]
    summary = {'motions': len(motions), 'executed_brakes': len(brake_joins),
        'rejected_brakes': sum(r['braking'] is not None and not r['braking']['executed'] for r in motions),
        'nominal_translation_acceleration_jump': distribution([r['nominal_max_translation_acceleration_jump'] for r in motions]),
        'nominal_rotation_acceleration_jump': distribution([r['nominal_max_rotation_acceleration_jump'] for r in motions]),
        'nominal_jerk_limit_ratio': distribution([r['nominal_max_jerk_limit_ratio'] for r in motions]),
        'brake_translation_acceleration_jump': distribution([r['reference_translation_acceleration_jump'] for r in brake_joins]),
        'brake_jerk_limit_ratio': distribution([r['max_jerk_limit_ratio'] for r in brake_joins]),
        'adjacent_motion_translation_acceleration_jump': distribution([r['reference_translation_acceleration_jump'] for r in joins])}
    return {'sources': sources, 'summary': summary, 'motions': motions, 'adjacent_motion_joins': joins,
        'scope': 'saved public-control reference audit; no new simulation, no training',
        'limitations': ['Nominal reference extrema are analytic source metrics; brake extrema reconstructed from saved initial derivatives.',
            'Brake reference reset is separate from the physically continuous measured position.',
            'Cross-motion joins require identical endpoint/start sensor states; gaps with other controls are unmeasured.',
            'Rotational brake resets are not subtracted across different rotation-vector coordinate origins.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit_choices(args.input)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary']))
