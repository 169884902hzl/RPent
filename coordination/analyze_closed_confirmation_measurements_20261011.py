"""Read-only diagnosis; closed confirmation verdicts are never recomputed."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INDEX = ROOT / 'coordination/grasp_geometry_confirmation_event_closed_20261010_r2/fiveclass/rows.jsonl'
OUT = ROOT / 'coordination/grasp_closed_measurement_diagnosis_20261011_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def contact_category(name):
    text = name.lower()
    if any(x in text for x in ('cabinet', 'drawer', 'microwave')):
        return 'cabinet_or_furniture'
    if any(x in text for x in ('table', 'floor')):
        return 'table_or_floor'
    return 'other_object'


def main():
    indexes = list(map(json.loads, INDEX.read_text().splitlines()))
    cache, descent, errors, missing, pan_unknown, replay = {}, [], [], [], [], []
    for item in indexes:
        path = Path(item['input']['path'])
        if path not in cache:
            if pin(path)['sha256'] != item['input']['sha256']:
                raise ValueError('closed input changed')
            cache[path] = path.read_text().splitlines()
        raw = json.loads(cache[path][item['line'] - 1])
        first = raw.get('first_attempt') or {}
        receipt = first.get('receipt') or {}
        phase = raw.get('private_grasp_phase') or first.get('private_grasp_phase') or {}
        common = {**item, 'output_dir': raw['output_dir'], 'closed_verdict_unchanged': True}
        if item['registered_v3'] is not True:
            replay.append({'index': item, 'case': raw['case']})
        if not phase.get('samples') and item['registered_v3'] is not True:
            missing.append({**common, 'trace_sample_count': 0,
                            'closure_executed': bool(receipt.get('analytic_close')),
                            'method': 'analytic' if receipt.get('analytic_grasp_plan') else 'pi05'})
        if item['group'] == 'frypan' and item['registered_v3'] is None:
            hold = first.get('private_setup_hold') or {}
            pan_unknown.append({**common, 'reference': hold.get('reference'),
                                'checks': (first.get('private_hold_truth_v3') or {}).get('checks')})
        if item['failure_reason'] == 'analytic_descend_not_reached':
            motions = [m for m in first.get('motion_evidence', []) if m.get('analytic_stage') == 'descend']
            move = motions[-1] if motions else {}
            trajectory = move.get('trajectory') or []
            contacts = [c for s in trajectory[-10:]
                        for c in (s.get('contact_and_joints') or {}).get('contacts', [])
                        if any('robot0' in str(c.get(k)) or 'gripper' in str(c.get(k))
                               for k in ('geom1', 'geom2'))]
            pairs = sorted({tuple(sorted((c['geom1'], c['geom2']))) for c in contacts})
            obstacle_names = sorted({name for pair in pairs for name in pair
                                     if 'robot0' not in name and 'gripper' not in name})
            evidence_saved = bool(trajectory) and all('contact_and_joints' in s for s in trajectory[-10:])
            classes = sorted({contact_category(name) for name in obstacle_names})
            classification = ('contact_evidence_missing' if not evidence_saved else
                              '+'.join(classes) if classes else 'no_collision_observed_servo_timeout')
            descent.append({**common, 'classification': classification,
                            'contact_attribution_is_observation_not_causal_proof': True,
                            'obstacle_names': obstacle_names, 'robot_contact_pairs': pairs,
                            'trajectory_samples': len(trajectory), 'last10': trajectory[-10:],
                            'final_dist_m': move.get('final_dist_m'),
                            'steps_used': move.get('steps_used'), 'max_steps': move.get('max_steps'),
                            'target_xyz': move.get('target_xyz')})
        if ((item['registered_v3'] is False and item['public'] is True) or
                (item['registered_v3'] is True and item['public'] is False)):
            errors.append({**common, 'error_direction': 'FP' if item['public'] else 'FN',
                           'receipt': receipt, 'verification_measurements': first.get('verification_measurements'),
                           'public_before': first.get('public_before'), 'public_after': first.get('public_after'),
                           'private_final_checks': (first.get('private_hold_truth_v3') or {}).get('checks'),
                           'whole_skill_samples_saved': len(phase.get('samples') or [])})
    if len(descent) != 30:
        raise ValueError(f'expected current 30 descent failures, observed {len(descent)}')
    OUT.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for name, rows in [('descent30', descent), ('verifier_fp_fn', errors),
                       ('missing_whole_skill_traces', missing), ('pan_unknown', pan_unknown),
                       ('development_replay_cases', replay)]:
        dest = OUT / (name + '.jsonl')
        dest.write_text(''.join(json.dumps(x) + '\n' for x in rows))
        artifacts[name] = {**pin(dest), 'n': len(rows)}
    report = {'producer': pin(Path(__file__)), 'closed_index': pin(INDEX),
              'closed_truth_counts': dict(Counter(str(x['registered_v3']) for x in indexes)),
              'descent30_classes': dict(Counter(x['classification'] for x in descent)),
              'fp_fn': dict(Counter(x['error_direction'] for x in errors)), 'artifacts': artifacts,
              'old_scores_recomputed': False, 'training_allowed': False,
              'interpretation': 'missing collision evidence stays unresolved; no IK or collision cause inferred'}
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
