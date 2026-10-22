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
    p.add_argument('--witness-positions', type=Path)
    p.add_argument('--native-witness-parents', action='store_true')
    p.add_argument('--seed-start', type=int, default=11020100)
    p.add_argument('--distractor', action='append', default=[])
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
        witnesses = defaultdict(list)
        if a.witness_positions is not None:
            for line in a.witness_positions.read_bytes().splitlines():
                position = json.loads(line)
                assert position['source_split'] == 'train' and not position['PRO'] and not position['confirmation']
                worker = json.loads(checked(position['source']).read_bytes())
                source = worker['case']
                assert source['diagnostic']['domain'] == 'original'
                for trial in worker['result'].get('trials', []):
                    if (trial.get('vla_variant', {}).get('name') == 'full_task'
                            and trial['success'] is True
                            and trial.get('truth_source') == 'unchanged_native_task_completion'):
                        witnesses[(source['episode']['suite'], source['episode']['task'])].append({
                            'worker': position['source'], 'trial_seed': trial['trial_seed'],
                            'parent_case': source['name']})
        if a.native_witness_parents:
            if a.witness_positions is None:
                raise ValueError('native-witness parent selection requires pinned original train records')
            eligible = {v['parent_case'] for options in witnesses.values() for v in options}
            groups = {category: [i for i in values if plan['cases'][i]['name'] in eligible]
                for category,values in groups.items()}
            if (any(len(values)<2 for values in groups.values())
                    or len(groups['bowl_transfer'])<3 or len(groups['box_transfer'])<3):
                raise ValueError('not enough original train parents with recorded native witnesses')
            indices = [i for values in groups.values() for i in values[:2]]
            indices += [groups['bowl_transfer'][2], groups['box_transfer'][2]]
        if not 11020000 <= a.seed_start <= 11029980:
            raise ValueError('pilot seeds must stay in the registered own-layout segment')
        record = {'parent': ref(a.parent), 'source': str(a.source),
            'registry': ref(a.registry), 'original_geometry': ref(a.original_geometry),
            'generator_files': [ref(a.source/'scripts/generate_bounded_train_layouts.py'),
                ref(a.source/'robots/libero/bounded_train_layouts.py')],
            'output': str(a.output), 'training': False, 'confirmation': False,
            'seed_segment': [a.seed_start, a.seed_start+19], 'policy_calls': 0,
            'selection': ('registered original train identity order with an existing native witness; no perturbed-policy outcomes used'
                if a.native_witness_parents else 'registered original train identity order; no new outcome selection'),
            'jobs': [{'case_index': index, 'seed': a.seed_start+j,
                'category': plan['cases'][index]['category'],
                'parent_case': plan['cases'][index]['name']} for j, index in enumerate(indices)]}
        if a.witness_positions is not None:
            record['witness_positions'] = ref(a.witness_positions)
            for job in record['jobs']:
                case = plan['cases'][job['case_index']]
                options = witnesses[(case['episode']['suite'], case['episode']['task'])]
                matched = next((v for v in options if v['parent_case'] == case['name']), None)
                if matched is not None:
                    job['native_witness'] = matched
        if a.distractor:
            record['distractors'] = a.distractor
            record['generator_files'].append(ref(a.source/'robots/libero/bounded_layout_distractors.py'))
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
        record['registry'], record['original_geometry'], native_witness=job.get('native_witness'),
        distractors=job.get('distractors', record.get('distractors', ())))
    print(json.dumps({'case': a.worker, 'seed': job['seed'],
        'state_sha256': result['state_sha256'],
        'predicate_witness': result['layout']['predicate_witness'], 'policy_calls': 0}))


if __name__ == '__main__':
    main()
