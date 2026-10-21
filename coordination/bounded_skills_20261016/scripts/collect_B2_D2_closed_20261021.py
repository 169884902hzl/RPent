"""Audit all independent B2 replays and pair their native results with A1-M."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref):
    assert reference(ref['path']) == ref
    return json.loads(Path(ref['path']).read_bytes())


def rate(values):
    known = [value for value in values if type(value) is bool]
    s, n = sum(known), len(known)
    if not n:
        return {'successes': 0, 'n': 0, 'unknown': len(values), 'wilson95': None}
    z = 1.959963984540054
    center = (s/n+z*z/(2*n))/(1+z*z/n)
    radius = z*math.sqrt((s/n)*(1-s/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return {'successes': s, 'n': n, 'unknown': len(values)-n,
        'rate': s/n, 'wilson95': [center-radius, center+radius]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--replay-preparation', type=Path, action='append', required=True)
    p.add_argument('--replay-results', type=Path, action='append', required=True)
    p.add_argument('--a1-table', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert len(a.replay_preparation) == len(a.replay_results) == 3
    with a.a1_table.open() as stream:
        a1 = {r['case']: r['A1_M_native_success'] == 'True' for r in csv.DictReader(stream)}
    assert len(a1) == 40 and sum(a1.values()) == 28
    rows, manifests, summaries, seen = [], [], {}, set()
    for preparation, results in zip(a.replay_preparation, a.replay_results):
        manifest_path = preparation/'manifest.json'
        plan = json.loads(manifest_path.read_bytes())
        assert len(plan['jobs']) == 40 and not plan['missing_parent_cases']
        manifests.append(reference(manifest_path))
        budget = plan['jobs'][0]['recovery_budget']
        assert budget not in seen
        seen.add(budget)
        for index, job in enumerate(plan['jobs']):
            assert job['recovery_budget'] == budget
            ptr = json.loads((results/f'closed_{index:03d}.json').read_bytes())
            summary_ref = {'path': ptr['summary'], 'sha256': ptr['sha256']}
            result = checked(summary_ref)
            parent = checked(job['parent_summary'])
            assert result['status'] == 'physical_result' and result['full_replay']
            assert result['case'] == job['case'] == parent['case']
            assert result['source_commit'] == plan['source_commit']
            assert result['initial_physics_sha256'] == result['parent_initial_physics_sha256']
            success = result['actual_full_replay_success']
            assert type(success) is bool
            case = job['case']['name']
            assert case in a1
            row = {'case': case, 'suite': job['case']['episode']['suite'],
                'recovery_budget': budget, 'A1_M_native_success': a1[case],
                'full_replay_success': success,
                'sampled_path_success': result['sampled_envelope_native_success'],
                'conditional_rate_product': result['conditional_rate_product'],
                'selection_reason': result['path_selection']['reason'],
                'private_rule_status': result['private_rule_status'],
                'unsupported': result['unsupported'],
                'failure_reasons': [x.get('reason') for x in result['full_replay'] if x.get('success') is not True],
                'sim_steps': sum(x['sim_steps'] for x in result['full_replay']),
                'decisions': sum(x['decisions'] for x in result['full_replay']),
                'replay_wall_s': result['independent_replay_wall_s'],
                'initial_physics_sha256': result['initial_physics_sha256'],
                'replay_summary': summary_ref, 'sampling_summary': job['parent_summary'],
                'sampling_source_commit': parent['source_commit'],
                'source_commit': result['source_commit'], 'training': False}
            rows.append(row)
        cohort = [row for row in rows if row['recovery_budget'] == budget]
        assert len({row['case'] for row in cohort}) == 40
        suites = defaultdict(list)
        for row in cohort:
            suites[row['suite']].append(row)
        summaries[budget] = {'native_independent_replay': rate([r['full_replay_success'] for r in cohort]),
            'sampled_paths': rate([r['sampled_path_success'] for r in cohort]),
            'A1_M': rate([r['A1_M_native_success'] for r in cohort]),
            'paired_outcomes': dict(Counter(f"A1={int(r['A1_M_native_success'])},B2={int(r['full_replay_success'])}" for r in cohort)),
            'by_suite': {s: {'replay': rate([r['full_replay_success'] for r in rs]),
                'sampled_paths': rate([r['sampled_path_success'] for r in rs])} for s, rs in suites.items()},
            'uncovered_private_rules': [r['case'] for r in cohort if r['private_rule_status'] != 'physical_result'],
            'improvements': [r['case'] for r in cohort if r['full_replay_success'] and not r['A1_M_native_success']],
            'regressions': [r['case'] for r in cohort if not r['full_replay_success'] and r['A1_M_native_success']]}
    assert seen == {0, 1, 2} and len(rows) == 120
    a.output.mkdir(parents=True, exist_ok=False)
    with (a.output/'episodes.jsonl').open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row)+'\n')
    report = {'source': 'measured B2 group comparisons and independent complete-path replays',
        'training': False, 'confirmation': False, 'evaluation_domain': 'D2',
        'A1_pairing_scope': 'same registered task and seed; not a common full-physics fork against A1',
        'sampled_scope': 'conditional sampled prefixes, not an exhaustive optimal-policy bound; unknown retained',
        'by_recovery_budget': summaries}
    (a.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    manifest = {'replay_plans': manifests, 'A1_M_table': reference(a.a1_table),
        'rows': reference(a.output/'episodes.jsonl'), 'summary': reference(a.output/'summary.json'),
        'collector': reference(Path(__file__)), 'closed_episodes': 120, 'training': False}
    (a.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
