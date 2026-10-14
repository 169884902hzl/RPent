"""Compare controls and geometry methods on identical state bytes and v3 labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

from coordination.summarize_registered_grasp_v3r9 import confusion, metric

LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--before-group', help='exact parent method in a multi-method report')
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = list(map(json.loads, (args.before / 'rows.jsonl').open()))
    if args.before_group:
        baseline = [r for r in baseline if r['group'] == args.before_group]
        if not baseline:
            raise ValueError('specified reference group is absent')
    indexed = {(r['type'], r['state_sha256']): r for r in baseline}
    if len(indexed) != len(baseline):
        raise ValueError('one reference trial per object type and registered state is required')
    groups, metadata, records, inputs = defaultdict(list), {}, [], []
    for parent in args.input:
        rows_path, manifest_path = parent / 'rows.jsonl', parent / 'manifest.json'
        document = json.loads(manifest_path.read_text())
        sources = {}
        for reference in document['plans']:
            path = Path(reference['path'])
            if pin(path)['sha256'] != reference['sha256']:
                raise ValueError('registered method plan changed')
            plan = json.loads(path.read_text())
            source = Path(plan['source_path'])
            if pin(source / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
                raise ValueError('method does not use the locked v3 predicate')
            group = path.parent.parent.parent.name + '/' + path.parent.parent.name
            sources[group] = {'plan': reference, 'source_identity': pin(source / 'source_identity_v3r9.json'),
                             'controller_files': [r for r in plan['source_snapshot']['files']
                                if r['relative_path'] in ('robots/libero/v5_runtime.py',
                                    'robots/libero/v5_analytic_grasp.py', 'robots/libero/v5_geometric_grasp.py',
                                    'robots/libero/v5_grasp_public_tracking.py', 'robots/libero/v5_grasp_geometry.py')],
                             'private_scorer_sha256': LOCKED_V3}
        for group, value in document['groups'].items():
            if group in metadata:
                raise ValueError('one closed evidence report per method required')
            metadata[group] = {'registered_n': value['registered_n'], **sources[group]}
        inputs.append({'records': pin(rows_path), 'manifest': pin(manifest_path)})
        for row in map(json.loads, rows_path.open()):
            previous = indexed[(row['type'], row['state_sha256'])]
            before, after = previous['registered_v3'], row['registered_v3']
            transition = ('unknown_in_pair' if before is None or after is None else
                          'improved' if before is False and after is True else
                          'regressed' if before is True and after is False else
                          'both_success' if before else 'both_failure')
            result = {**row, 'before_v3': before, 'v3_transition': transition,
                'before_case': previous['case'], 'before_input': {'path': previous['input'],
                    'sha256': previous['input_sha256'], 'line': previous['line']}}
            records.append(result)
            groups[row['group']].append(result)
    summaries = {}
    for group, info in metadata.items():
        items = groups[group]
        if len({r['state_sha256'] for r in items}) != len(items):
            raise ValueError('duplicate physical state within method')
        n = info['registered_n']
        sim_steps = [r['sim_steps'] for r in items if isinstance(r.get('sim_steps'), (int, float))]
        summaries[group] = {**info, 'recorded_n': len(items), 'pending_n': n-len(items),
            'v3_success_all_registered': metric(sum(r['registered_v3'] is True for r in items), n),
            'v3_truth_unknown': sum(r['registered_v3'] is None for r in items),
            'public_verifier_recorded': confusion(items, 'registered_v3'),
            'pair_transitions': dict(Counter(r['v3_transition'] for r in items)),
            'failure_reasons': dict(Counter(r['failure_reason'] for r in items)),
            'sim_steps_median': statistics.median(sim_steps) if sim_steps else None,
            'regressed_cases': [r['case'] for r in items if r['v3_transition'] == 'regressed']}
    args.output.mkdir(parents=True, exist_ok=False)
    rows_path = args.output / 'rows.jsonl'
    rows_path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    report = {'before': pin(args.before / 'rows.jsonl'), 'before_group': args.before_group, 'inputs': inputs,
        'producer': pin(Path(__file__)), 'records': pin(rows_path), 'groups': summaries,
        'truth_rule_sha256': LOCKED_V3, 'old_exclusive_v2_not_relabelled': True,
        'limits': ['These are same-state development selections, not independent confirmations.',
                   'Unknown truth and unmeasured public verdict remain in denominators.',
                   'Pending cases are shown separately and cannot establish a method success rate.'],
        'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({g: {'success': v['v3_success_all_registered'], 'recorded': v['recorded_n'],
        'pending': v['pending_n'], 'paired': v['pair_transitions']} for g, v in summaries.items()}))


if __name__ == '__main__':
    main()
