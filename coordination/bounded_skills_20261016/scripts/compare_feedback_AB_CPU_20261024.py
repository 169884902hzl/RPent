"""Locate the first logged VLA input/prediction difference in the A/B pair."""
import argparse
import hashlib
import json
from pathlib import Path


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'case': 'libero_10_task_t2_s40', 'case_directory': 'case036',
        'oracle_private_predicates_available_in_both_arms': True, 'sources': []}
    for ledger in ('vla_inputs.jsonl', 'vla_predictions.jsonl'):
        paths = [args.run / (arm + '_r1/case036') / ledger
            for arm in ('oracle_A', 'oracle_AB')]
        result['sources'].extend(reference(path) for path in paths)
        arrays = [[json.loads(line) for line in path.read_text().splitlines()] for path in paths]
        first = None
        for index, (a, b) in enumerate(zip(*arrays)):
            if a == b:
                continue
            first = {'block_index_zero_based': index, 'sampling_seed_A': a['sampling_seed'],
                'sampling_seed_AB': b['sampling_seed'],
                'different_keys': sorted(key for key in a.keys() | b.keys() if a.get(key) != b.get(key))}
            if ledger == 'vla_inputs.jsonl':
                first['different_observation_fields'] = sorted(key for key in a['fields'].keys() | b['fields'].keys()
                    if a['fields'].get(key) != b['fields'].get(key))
            else:
                first['first_action_max_abs_delta'] = max(abs(x-y) for x, y in zip(a['first_action'], b['first_action']))
            break
        result[ledger] = {'blocks_A': len(arrays[0]), 'blocks_AB': len(arrays[1]), 'first_difference': first}
    result['interpretation'] = ('The logged policy observations/predictions diverge despite matching initial state and seeds. '
        'Both rule oracles already had private predicate access; the one-episode difference is not evidence of B information gain. '
        'Hashes locate the first recorded difference but do not establish its rendering/numerical cause.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'sources'}))


if __name__ == '__main__':
    main()
