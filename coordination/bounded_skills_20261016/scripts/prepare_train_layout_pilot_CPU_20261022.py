"""Preregister twenty own-layout CPU constructions; policy evaluation is separate."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(reference):
    path = Path(reference['path'])
    assert ref(path) == reference
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--registration', type=Path, required=True)
    p.add_argument('--parent', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--registry', type=Path)
    p.add_argument('--original-geometry', type=Path)
    p.add_argument('--worker', type=int)
    a = p.parse_args()
    if a.worker is None:
        plan = json.loads(a.parent.read_bytes())
        assert not plan['training'] and not plan['confirmation']
        groups = defaultdict(list)
        for i, case in enumerate(plan['cases']):
            assert case['diagnostic']['domain'] == 'original'
            groups[case['category']].append(i)
        # Two states in each of nine registered train categories, plus a
        # third bowl and box. Selection never consults perturbation outcomes.
        indices = [i for values in groups.values() for i in values[:2]]
        indices += [groups['bowl_transfer'][2], groups['box_transfer'][2]]
        assert len(indices) == len(set(indices)) == 20
        record = {'parent': ref(a.parent), 'source': str(a.source),
            'registry': ref(a.registry), 'original_geometry': ref(a.original_geometry),
            'generator_files': [ref(a.source/'scripts/generate_bounded_train_layouts.py'),
                ref(a.source/'robots/libero/bounded_train_layouts.py')],
            'output': str(a.output), 'training': False, 'confirmation': False,
            'seed_segment': [11020100, 11020119], 'policy_calls': 0,
            'selection': 'registered original train identity order; no new outcome selection',
            'jobs': [{'case_index': index, 'seed': 11020100+j,
                'category': plan['cases'][index]['category'],
                'parent_case': plan['cases'][index]['name']} for j, index in enumerate(indices)]}
        a.registration.parent.mkdir(parents=True, exist_ok=True)
        with a.registration.open('x') as stream:
            json.dump(record, stream, indent=2)
        print(json.dumps({'registration': ref(a.registration), 'states': 20,
            'seed_segment': record['seed_segment'], 'CPU_only': True}))
        return
    record = json.loads(a.registration.read_bytes())
    assert str(a.source) == record['source']
    for reference in record['generator_files']:
        checked(reference)
    plan = json.loads(checked(record['parent']).read_bytes())
    for key in ('registry', 'original_geometry'):
        checked(record[key])
    job = record['jobs'][a.worker]
    sys.path.insert(0, str(a.source))
    import robots.libero.env_server  # Configure MuJoCo before its first import.
    from scripts.generate_bounded_train_layouts import generate_case
    output = Path(record['output'])/f'case{a.worker:03d}'
    result = generate_case(plan, job['case_index'], job['seed'], output,
        record['registry'], record['original_geometry'])
    print(json.dumps({'case': a.worker, 'seed': job['seed'],
        'state_sha256': result['state_sha256'],
        'predicate_witness': result['layout']['predicate_witness'], 'policy_calls': 0}))


if __name__ == '__main__':
    main()
