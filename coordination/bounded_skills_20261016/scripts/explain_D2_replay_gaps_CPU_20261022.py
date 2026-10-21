"""Explain each closed sampled-success/replay-failure row from its raw records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def load(ref):
    raw = Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('retained artifact changed')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_bytes())
    rows = []
    for item in audit['disagreements']:
        sampling, replay = load(item['sampling_summary']), load(item['replay_summary'])
        sample_trials = [t for s in sampling.get('subtasks', []) for t in s['trials']]
        branches = []
        for compact, trial in zip(item['branches'], replay['full_replay']):
            truth = load(trial['evidence'])
            v3 = truth.get('truth_v3', {})
            checks = v3.get('checks', [])
            successful = [s for s in compact['matching_sample_trials'] if s['success'] is True]
            matched = [s for s in sample_trials if any(s['trial_seed'] == t['trial_seed']
                and s['subtask']['id'] == t['subtask']['id'] for t in successful)]
            wire = trial.get('vla_inputs', [])[:1]
            pred = trial.get('vla_predictions', [])[:1]
            comparisons = []
            for sample in matched:
                sample_wire, sample_pred = sample.get('vla_inputs', [])[:1], sample.get('vla_predictions', [])[:1]
                comparisons.append({'sample_seed': sample['trial_seed'],
                    'same_complete_initial': sample['initial_physics_sha256'] == trial['initial_physics_sha256'],
                    'same_first_wire': bool(wire and sample_wire and
                        wire[0]['wire_observation_sha256'] == sample_wire[0]['wire_observation_sha256']),
                    'same_first_action_block': bool(pred and sample_pred and
                        pred[0]['actions_sha256'] == sample_pred[0]['actions_sha256'])})
            controls = []
            for line in Path(trial['choices']['path']).read_bytes().splitlines():
                choice = json.loads(line)
                for detail in choice.get('execution_details', []):
                    e = detail.get('execution', {})
                    if 'blocks_used' in e:
                        controls.append({'stop_reason': e.get('stop_reason'),
                            'skill_stop_reason': e.get('skill_stop_reason'),
                            'steps_used': e.get('steps_used'), 'blocks_used': e.get('blocks_used'),
                            'handoff_steps': e.get('handoff', {}).get('steps_used'),
                            'post_handoff_completed': e.get('post_handoff_measurement', {}).get('completed')})
            branches.append({'subtask': trial['subtask']['id'], 'method': trial['method'],
                'success': trial['success'], 'reason': trial['reason'], 'seed': trial['trial_seed'],
                'sample_comparisons': comparisons, 'failure_receipts': compact['failure_receipts'],
                'vla_stops': controls, 'truth_source': trial.get('truth_source'),
                'private_grasp_summary': None if not v3 else {
                    'success': v3['success'], 'n': len(checks),
                    'dual_finger_samples': sum(c.get('dual_finger_contact') is True for c in checks),
                    'clearance_min_m': min(c['clearance_m'] for c in checks),
                    'relative_displacement_max_m': max(c['relative_com_displacement_m'] for c in checks)},
                'evidence': trial['evidence'], 'choices': trial['choices']})
        failed = next((b for b in branches if b['success'] is not True), None)
        if item['endpoint_success_but_final_false']:
            cause = 'native_solver_phase_lost_at_endpoint_restore'
        elif failed['reason'] == 'measured_success_after_handoff':
            cause = 'public_completion_false_positive_against_private_grasp_v3'
        elif any(r['skill'] != 'call_vla' for r in failed['failure_receipts']):
            cause = 'own_skill_zero_control_guard_then_observation_collision'
        elif failed['reason'] == 'requested_vla_variant_unavailable':
            cause = 'selected_variant_unavailable_after_partial_replay'
        elif any(v['stop_reason'] == 'completion_lost_during_handoff' for v in failed['vla_stops']):
            cause = 'handoff_completion_not_retained'
        elif any(v['stop_reason'] == 'no_progress_blocks' for v in failed['vla_stops']):
            cause = 'independent_vla_replay_no_progress_stop'
        else:
            cause = 'independent_vla_replay_block_budget'
        rows.append({'case': item['case'], 'recovery_budget': item['recovery_budget'],
            'classification': cause, 'branches': branches,
            'sampling_summary': item['sampling_summary'], 'replay_summary': item['replay_summary']})
    result = {'scope': 'closed D2 raw-artifact explanation; independent seeds are not deterministic replays',
        'training': False, 'rescore': False, 'rows': rows,
        'counts': dict(Counter(row['classification'] for row in rows))}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'rows.json').write_text(json.dumps(result, indent=2)+'\n')
    text = ['| 恢复档 | 状态 | 第一个失败子任务 | 原件支持的原因 |', '|---:|---|---|---|']
    for row in rows:
        failed = next((b for b in row['branches'] if b['success'] is not True), None)
        text.append(f"| {row['recovery_budget']} | {row['case']} | {failed['subtask'] if failed else '原生终态恢复'} | {row['classification']} |")
    (args.output/'table.md').write_text('\n'.join(text)+'\n')
    print(json.dumps({'rows': len(rows), 'counts': result['counts'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
