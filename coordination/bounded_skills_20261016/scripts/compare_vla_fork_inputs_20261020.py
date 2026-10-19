"""Compare recorded policy inputs/actions for the same registered fork and seed."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def collect(label, root):
    rows = []
    for path in sorted(root.rglob('vla_inputs.jsonl')):
        directory = path.parent
        while directory != root and not (directory/'assignment.json').exists():
            directory = directory.parent
        assignment = directory/'assignment.json'
        if not assignment.exists():
            raise ValueError(f'input ledger has no owning assignment: {path}')
        owner = json.loads(assignment.read_bytes())
        manifest_bytes = Path(owner['manifest']['path']).read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != owner['manifest']['sha256']:
            raise ValueError(f'assignment manifest changed: {assignment}')
        manifest = json.loads(manifest_bytes)
        case = owner['case']
        inputs = read_lines(path)
        predictions_path = path.with_name('vla_predictions.jsonl')
        predictions = read_lines(predictions_path) if predictions_path.exists() else []
        if not inputs:
            continue
        checkpoint = case['diagnostic']['branchpoint']
        rows.append({'label': label, 'case': case['name'],
            'source_commit': manifest['source_commit'],
            'startup': owner['startup'], 'input_path': str(path),
            'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'prediction_path': str(predictions_path),
            'branchpoint_sha256': checkpoint['sha256'],
            'sampling_seed': inputs[0]['sampling_seed'],
            'inputs': inputs, 'predictions': predictions})
    return rows


def compare(left, right):
    n = min(len(left['inputs']), len(right['inputs']))
    m = min(len(left['predictions']), len(right['predictions']))
    input_difference = next((i for i in range(n) if left['inputs'][i] != right['inputs'][i]), None)
    prediction_difference = next((i for i in range(m)
        if left['predictions'][i] != right['predictions'][i]), None)
    changed = []
    if input_difference is not None:
        a, b = left['inputs'][input_difference], right['inputs'][input_difference]
        changed = sorted(k for k in a['fields'].keys() | b['fields'].keys()
            if a['fields'].get(k) != b['fields'].get(k))
    return {'left': left['input_path'], 'right': right['input_path'],
        'branchpoint_sha256': left['branchpoint_sha256'], 'sampling_seed': left['sampling_seed'],
        'input_counts': [len(left['inputs']), len(right['inputs'])],
        'prediction_counts': [len(left['predictions']), len(right['predictions'])],
        'common_input_calls': n, 'common_prediction_calls': m,
        'first_input_mismatch': input_difference, 'first_changed_input_fields': changed,
        'first_prediction_mismatch': prediction_difference,
        'recorded_prefix_equal': bool(n and m and input_difference is None and prediction_difference is None),
        'scope': 'recorded inference prefix; not unobserved calls or full branch success'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', action='append', required=True, metavar='LABEL=ROOT')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for group in args.group:
        label, value = group.split('=', 1)
        rows.extend(collect(label, Path(value).resolve(strict=True)))
    pairs = [compare(a, b) for a, b in itertools.combinations(rows, 2)
        if (a['branchpoint_sha256'], a['sampling_seed']) == (b['branchpoint_sha256'], b['sampling_seed'])]
    report = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ledgers': [{k: v for k, v in row.items() if k not in {'inputs', 'predictions'}} for row in rows],
        'pairs': pairs, 'matching_pairs': sum(row['recorded_prefix_equal'] for row in pairs),
        'pair_count': len(pairs), 'physics_steps': 0, 'training': False}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('pair_count', 'matching_pairs')}))


if __name__ == '__main__':
    main()
