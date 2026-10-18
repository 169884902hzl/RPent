"""Recount the registered same-state boundary-rule comparison as it completes."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.summarize_bounded_probes import distribution, feasibility


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(root, tag):
    base = root/'coordination/bounded_skills_20261016'
    receipt_path = base/'reports'/f'{tag}_full_submission.json'
    receipt = json.loads(receipt_path.read_text())
    manifest = Path(receipt['manifest']['path'])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == receipt['manifest']['sha256']
    cases = json.loads(manifest.read_text())['cases']
    files, results, errors, waiting = [], {}, [], []
    histograms = defaultdict(Counter)
    eligible = defaultdict(Counter)
    cutoffs = defaultdict(Counter)
    indices = receipt.get('indices', list(range(len(cases))))
    for index in indices:
        case = cases[index]
        directory = root/'results/bounded_skills/feasibility_20261017'/f"job{receipt['job']}_{index}"
        path = directory/'episodes.jsonl'
        rows = read_rows(path)
        physical = [row for row in rows if row.get('status') == 'physical_result']
        if physical:
            files.append(path)
        errors.extend({'shard': index, 'record': str(path), **row} for row in rows
                      if row.get('status') not in {'physical_result', 'startup_physical'})
        by_arm = {}
        for row in physical:
            assert row['case'] == case and row['pi05_calls'] == 0 and not row['training']
            arm = row['arm']
            assert arm not in by_arm, (index, arm)
            by_arm[arm] = row
            arm_directory = directory/(case['name']+'_'+arm)
            for choice in read_rows(arm_directory/'choices.jsonl'):
                if 'receipts' not in choice:
                    continue
                selected_ids = choice['decision']['candidate_ids']
                receipts = choice['receipts']
                histograms[arm][sum(r['steps_used'] > 0 for r in receipts)] += 1
                for position, action in enumerate(receipts):
                    if position+1 < len(selected_ids):
                        eligible[arm][action['skill']] += 1
                chunk = choice['chunk_execution']
                if chunk['discarded_ids']:
                    skill = chunk['interrupted_skill']
                    cutoffs[arm][(skill, chunk['stop_reason'])] += 1
        if set(by_arm) == {'oracle_k4', 'oracle_k4_legacy'}:
            results[index] = by_arm
        else:
            waiting.append({'shard': index, 'case': case['name'], 'complete_arms': list(by_arm)})
    pairs = []
    for index, arms in results.items():
        new, old = arms['oracle_k4'], arms['oracle_k4_legacy']
        outcome = ('both_success' if old['success'] else 'improved') if new['success'] else (
            'regressed' if old['success'] else 'both_failed')
        pairs.append({'shard': index, 'case': new['case'], 'outcome': outcome,
            'new': {key: new.get(key) for key in ('success', 'decisions', 'sim_steps', 'wall_s', 'failure_phase', 'terminal_category')},
            'old': {key: old.get(key) for key in ('success', 'decisions', 'sim_steps', 'wall_s', 'failure_phase', 'terminal_category')},
            'delta': {key: new[key]-old[key] for key in ('decisions', 'sim_steps', 'wall_s')}})
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair['case']['category']].append(pair)
    paired_summary = {category: {'n': len(group),
        'outcomes': dict(Counter(pair['outcome'] for pair in group)),
        'decision_delta': distribution([pair['delta']['decisions'] for pair in group]),
        'simulation_step_delta': distribution([pair['delta']['sim_steps'] for pair in group])}
        for category, group in groups.items()}
    truncations = {}
    for arm, counts in eligible.items():
        truncations[arm] = {skill: {'eligible_with_suffix': n,
            'interrupted': sum(count for (s, _), count in cutoffs[arm].items() if s == skill),
            'rate': sum(count for (s, _), count in cutoffs[arm].items() if s == skill)/n,
            'reasons': {reason: count for (s, reason), count in cutoffs[arm].items() if s == skill}}
            for skill, n in counts.items()}
    return {'source_commit': receipt['source_commit'], 'snapshot': receipt['snapshot'],
        'submission': receipt, 'scope': 'original-task development; identical source and state; only static chunk boundary rule differs',
        'registered_states': len(indices), 'closed_pairs': len(pairs),
        'outcomes': dict(Counter(pair['outcome'] for pair in pairs)),
        'paired_by_category': paired_summary, 'pairs': pairs, 'pending': waiting,
        'execution_errors': errors, 'actual_actions_per_decision_histogram': dict(histograms),
        'midchunk_truncations_by_eligible_skill': truncations,
        'physical_result_cohorts': feasibility(files),
        'limitations': ['Unfinished arms are not paired results.',
            'Native success may legitimately discard a suffix; stop reasons remain separate.',
            'Existing smooth_reference metrics cover nominal splines, not all braking or cross-skill joins.'],
        'training': False, 'confirmation': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/public/home/sunyihan/rpent_libero_eval'))
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    report = summarize(args.root, args.tag)
    output = args.root/'coordination/bounded_skills_20261016/reports'/f'{args.tag}_paired_latest.json'
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('registered_states', 'closed_pairs', 'outcomes',
        'paired_by_category', 'actual_actions_per_decision_histogram', 'midchunk_truncations_by_eligible_skill')}))
