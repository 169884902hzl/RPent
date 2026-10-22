"""Trace the three requested D2 issues through closed, immutable artifacts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def load(ref):
    raw = Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('artifact checksum changed: '+ref['path'])
    return json.loads(raw)


def compact(trial):
    keys = ('method', 'subtask', 'trial_seed', 'success', 'reason', 'sim_steps',
        'decisions', 'source_public_id', 'target_public_id', 'vla_inference_calls',
        'vla_variant', 'selected_vla_variant', 'truth_source', 'initial_physics_sha256',
        'endpoint', 'evidence', 'choices')
    return {key: trial[key] for key in keys if key in trial}


def params(trial):
    variant = trial.get('vla_variant')
    return variant.get('parameters') if isinstance(variant, dict) else None


def replay_choices(replay, sampling):
    """Read both the separate-path and original in-batch replay formats."""
    if 'path_selection' in replay:
        return replay['path_selection'].get('choices', [])
    return [{'subtask': row['subtask'], **{key: row['selection'][key]
        for key in ('method', 'vla_parameters', 'vla_variant')
        if key in row['selection']}} for row in sampling.get('subtasks', [])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.episodes.read_bytes()
    unavailable, disagreements = [], []
    for episode in map(json.loads, raw.splitlines()):
        sampling, replay = load(episode['sampling_summary']), load(episode['replay_summary'])
        ident = {key: episode[key] for key in ('case', 'recovery_budget')}
        for subtask in sampling.get('subtasks', []):
            for trial in subtask['trials']:
                if trial.get('reason') == 'requested_vla_variant_unavailable':
                    row = ident | compact(trial)
                    row['binding_missing'] = (trial.get('source_public_id') is None
                        or bool(subtask['subtask'].get('target_symbol'))
                        and trial.get('target_public_id') is None)
                    row['branchpoint'] = trial.get('branchpoint')
                    unavailable.append(row)
        if not (episode['sampled_path_success'] is True
                and episode['full_replay_success'] is False):
            continue
        branches = []
        choices = replay_choices(replay, sampling)
        for index, trial in enumerate(replay['full_replay']):
            choice = choices[index] if index < len(choices) else {}
            subtask = next((s for s in sampling.get('subtasks', [])
                if s['subtask']['id'] == trial['subtask']['id']), None)
            matches = [] if subtask is None else [s for s in subtask['trials']
                if s['method'] == trial['method'] and (trial['method'] != 'call_vla'
                    or params(s) == choice.get('vla_parameters'))]
            item = {'replay': compact(trial), 'selected_choice': choice,
                'matching_sample_trials': [compact(s) for s in matches],
                'same_initial_as_any_matching_sample': any(
                    s['initial_physics_sha256'] == trial['initial_physics_sha256'] for s in matches),
                'same_seed_as_any_matching_sample': any(
                    s['trial_seed'] == trial['trial_seed'] for s in matches)}
            first = trial.get('vla_inputs', [])[:1]
            item['first_wire_input_equal_to_matching_samples'] = [
                bool(first and s.get('vla_inputs') and
                    first[0]['wire_observation_sha256'] == s['vla_inputs'][0]['wire_observation_sha256'])
                for s in matches]
            if trial.get('choices'):
                log = Path(trial['choices']['path']).read_bytes()
                if hashlib.sha256(log).hexdigest() != trial['choices']['sha256']:
                    raise ValueError('choice log checksum changed')
                item['failure_receipts'] = [{key: r.get(key) for key in
                    ('skill', 'outcome', 'stop_reason', 'steps_used', 'phase')}
                    for line in log.splitlines() for r in json.loads(line).get('receipts', [])
                    if r['outcome'] != 'success']
            branches.append(item)
        terminal_loss = bool(replay['full_replay'] and replay['full_replay'][-1]['success'] is True)
        disagreements.append(ident | {'sampling_summary': episode['sampling_summary'],
            'replay_summary': episode['replay_summary'], 'branches': branches,
            'endpoint_success_but_final_false': terminal_loss,
            'classification': ('endpoint_restore_predicate_difference' if terminal_loss
                else 'independent_replay_branch_failed'),
            'cause_certainty': 'artifact-level symptom; restore/input/control diagnosis required'})
    counts = Counter((row['case'], row['binding_missing']) for row in unavailable)
    report = {'scope': 'closed D2 CPU artifact audit; no rescore or new simulation',
        'training': False, 'confirmation': False, 'episodes': str(args.episodes),
        'episodes_sha256': hashlib.sha256(raw).hexdigest(),
        'unavailable_count': len(unavailable),
        'unavailable_binding_missing': sum(r['binding_missing'] for r in unavailable),
        'unavailable_by_case': [{'case': case, 'binding_missing': missing, 'n': count}
            for (case, missing), count in sorted(counts.items())],
        'unavailable': unavailable, 'sample_success_replay_failure_count': len(disagreements),
        'disagreements': disagreements}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: value for key, value in report.items()
        if key not in ('unavailable', 'disagreements')}))


if __name__ == '__main__':
    main()
