"""Classify saved servo traces, retaining evidence and unresolved causes."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    indexes = [json.loads(line) for line in (args.summary / 'rows.jsonl').open()]
    cache, rows = {}, []
    for index in indexes:
        path = Path(index['input'])
        if path not in cache:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != index['input_sha256']:
                raise ValueError('physical ledger changed')
            cache[path] = data.splitlines()
        raw = json.loads(cache[path][index['line'] - 1])
        first = raw.get('first_attempt') or {}
        for move in first.get('motion_evidence') or []:
            stage = move.get('analytic_stage')
            if not stage:
                continue
            samples = (move.get('trajectory') or [])[-10:]
            positions = [s.get('eef_pos', s.get('eef')) for s in samples]
            positions = [p for p in positions if isinstance(p, list) and len(p) == 3]
            distances = [s.get('dist_to_target_m', s.get('dist')) for s in samples]
            distances = [d for d in distances if isinstance(d, (int, float))]
            diagnostics = [s.get('contact_and_joints') or {} for s in samples]
            contacts = [c for d in diagnostics for c in d.get('contacts', [])
                        if any('robot0' in str(c.get(k)) or 'gripper' in str(c.get(k))
                               for k in ('geom1', 'geom2'))]
            pairs = sorted(set(tuple(sorted((c['geom1'], c['geom2']))) for c in contacts))
            margins = [j['limit_margin_rad'] for d in diagnostics for j in d.get('joints', [])
                       if isinstance(j.get('limit_margin_rad'), (float, int))]
            span = max((math.dist(p, q) for p in positions for q in positions), default=None)
            progress = distances[0] - distances[-1] if len(distances) > 1 else None
            exhausted = move.get('actions_used') == move.get('max_steps')
            if not positions:
                classification = 'trace_missing'
            elif not exhausted:
                classification = 'servo_stopped_before_step_cap'
            elif span is not None and span > .002 and abs(progress or 0) < .001:
                classification = 'step_cap_with_motion_but_no_net_progress'
            elif pairs:
                classification = 'step_cap_stalled_with_robot_contact_evidence'
            elif margins and min(margins) < .02:
                classification = 'step_cap_near_joint_limit'
            elif progress is not None and progress > .001:
                classification = 'step_cap_still_approaching'
            else:
                classification = 'step_cap_stalled_cause_unresolved'
            rows.append({'case': index['case'], 'layout_seed': index['layout_seed'],
                'input': index['input'], 'input_sha256': index['input_sha256'], 'line': index['line'],
                'stage': stage, 'failure_reason': index['failure_reason'],
                'registered_v3': index['registered_v3'], 'public': index['public'],
                'classification': classification, 'final_dist_m': move['final_dist_m'],
                'last10_span_m': span, 'last10_net_progress_m': progress,
                'steps_used': move['steps_used'], 'actions_used': move.get('actions_used'),
                'max_steps': move.get('max_steps'), 'final_yaw_err': move.get('final_yaw_err'),
                'final_pitch': move.get('final_pitch'), 'robot_contact_pairs': pairs,
                'min_joint_limit_margin_rad': min(margins) if margins else None,
                'last10_positions': positions, 'last10_distances': distances,
                'target_xyz': move.get('target_xyz'),
                'IK_failure_not_inferred_from_tracking_error': True,
                'diagnostic_private_contacts_not_used_for_runtime_motion': True})
    failures = [r for r in rows if r['failure_reason'] == 'analytic_' + r['stage'] + '_not_reached']
    measured_spans = [r['last10_span_m'] for r in failures if r['last10_span_m'] is not None]
    report = {'input_summary': str(args.summary), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'stages': len(rows), 'failure_stage_count': len(failures),
        'failure_classes': dict(Counter(r['classification'] for r in failures)),
        'failure_robot_contact_cases': sum(bool(r['robot_contact_pairs']) for r in failures),
        'failure_distance_median_m': statistics.median(r['final_dist_m'] for r in failures) if failures else None,
        'failure_last10_span_median_m': statistics.median(measured_spans) if measured_spans else None,
        'failure_with_measured_last10_span_count': len(measured_spans),
        'diagnostic_only': True, 'qualification_claim': False}
    args.output.mkdir(exist_ok=False, parents=True)
    (args.output / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
