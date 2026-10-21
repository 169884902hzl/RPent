"""Compare closed B2 development replays with the frozen A1-M forty cases."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    d = 1 + z*z/n
    centre = (k/n + z*z/(2*n))/d
    half = z*math.sqrt(k*(n-k)/n**3 + z*z/(4*n*n))/d
    return [centre-half, centre+half]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--a1', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args()
    original = json.loads(a.a1.read_bytes())
    a1 = {row['case']: row for row in original['episodes'] if row['group'] == 'A1-M'}
    assert len(a1) == 40 and sum(row['native_success'] for row in a1.values()) == 28
    rows, reports = [], {}
    for budget in (0, 1, 2):
        directory = a.root / f'D2_recovery{budget}'
        closed = {}
        for path in sorted(directory.glob('closed_*.json')):
            pointer = json.loads(path.read_bytes())
            summary = Path(pointer['summary'])
            assert pointer['sha256'] == ref(summary)['sha256']
            data = json.loads(summary.read_bytes())
            sampled = data
            if 'parent_summary' in data:
                parent = Path(data['parent_summary']['path'])
                assert ref(parent) == data['parent_summary']
                sampled = json.loads(parent.read_bytes())
            name = data['case']['name']
            assert name in a1 and name not in closed
            replay = data.get('full_replay', [])
            if not replay:
                raise ValueError(f'no actual replay recorded: {summary}')
            assert type(data['actual_full_replay_success']) is bool
            row = {'case': name, 'suite': data['case']['episode']['suite'],
                'recovery_budget': budget, 'source_commit': data['source_commit'],
                'summary': ref(summary), 'A1_M_success': a1[name]['native_success'],
                'sampling_source_commit': sampled['source_commit'],
                'parent_sampling_summary': data.get('parent_summary'),
                'initial_physics_sha256': data.get('initial_physics_sha256'),
                'success': data['actual_full_replay_success'], 'status': data['status'],
                'sampled_envelope_success': data.get('sampled_envelope_native_success')
                    if data.get('conditional_rate_product') is not None else None,
                'conditional_rate_product': data.get('conditional_rate_product'),
                'replay_records': len(replay), 'replay_sim_steps': sum(t.get('sim_steps', 0) for t in replay),
                'replay_wall_s': data.get('independent_replay_wall_s'),
                'replay_stop_reasons': [t.get('reason') for t in replay],
                'subtask_selections': [{'subtask': s['subtask'], 'selection': s['selection'],
                    'trials': [{'method': t['method'], 'variant': t.get('vla_variant'),
                        'success': t['success'], 'sim_steps': t.get('sim_steps'),
                        'vla_inference_calls': t.get('vla_inference_calls'), 'reason': t.get('reason')}
                        for t in s['trials']]} for s in sampled.get('subtasks', [])]}
            rows.append(row)
            closed[name] = row
        missing = sorted(set(a1)-set(closed))
        if missing and not a.allow_incomplete:
            raise ValueError(f'recovery{budget}: {len(missing)} missing cases')
        values = list(closed.values())
        k, n = sum(row['success'] for row in values), len(values)
        pairs = Counter(('T' if row['A1_M_success'] else 'F') + ('T' if row['success'] else 'F') for row in values)
        known_bound = [row for row in values if row['sampled_envelope_success'] is not None]
        reports[str(budget)] = {'closed': n, 'success': k, 'wilson95': wilson(k, n),
            'missing': missing, 'paired_counts_A1_then_B2': dict(pairs),
            'improvements': [r['case'] for r in values if not r['A1_M_success'] and r['success']],
            'regressions': [r['case'] for r in values if r['A1_M_success'] and not r['success']],
            'sampled_bound_known': len(known_bound),
            'sampled_bound_success': sum(r['sampled_envelope_success'] for r in known_bound),
            'unknown_private_rule_cases': [r['case'] for r in values if r['sampled_envelope_success'] is None],
            'zero_replay_step_cases': [r['case'] for r in values if not r['replay_sim_steps']],
            'sources': sorted({r['source_commit'] for r in values}),
            'by_suite': {suite: {'n': len(group), 'success': sum(r['success'] for r in group),
                'wilson95': wilson(sum(r['success'] for r in group), len(group)),
                'A1_M_success_on_same_closed_cases': sum(r['A1_M_success'] for r in group)}
                for suite in sorted({r['suite'] for r in values})
                for group in [[r for r in values if r['suite'] == suite]]}}
    a.output.mkdir(parents=True, exist_ok=False)
    path = a.output/'paired_cases.jsonl'
    path.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
    manifest = {'training': False, 'confirmation': False, 'domain': 'D2_eval_only',
        'complete': all(not r['missing'] for r in reports.values()), 'recovery': reports,
        'A1_M': {'success': 28, 'n': 40, 'source': ref(a.a1)}, 'rows': ref(path),
        'scope': 'independent native full replay; sampled envelope is a separate diagnostic, not a measured episode success rate'}
    (a.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
