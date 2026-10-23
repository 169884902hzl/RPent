"""Forward exact completed tail results into their registered dispatcher slots."""
import argparse
import hashlib
import json
from pathlib import Path


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.registration.read_bytes())
    drain = json.loads((args.registration.parent/'redistribution4_drain_complete.json').read_bytes())
    assert drain['interrupted_episodes'] == 0
    linked = []
    for shard in plan['rows']:
        manifest = Path(shard['manifest']['path'])
        assert reference(manifest) == shard['manifest']
        panel = json.loads(manifest.read_bytes())
        for index, mapping in enumerate(shard['mapping']):
            pointer = Path(shard['output'])/f'closed_{index:03d}.json'
            closed = json.loads(pointer.read_bytes())
            summary = Path(closed['summary'])
            assert reference(summary)['sha256'] == closed['sha256']
            data = json.loads(summary.read_bytes())
            assert data['source_commit'] == plan['source_commit']
            assert data['case'] == panel['jobs'][index]['case'] == mapping['job']['case']
            assert data['restored_original_subtask_start']['same_captured_physics']
            target = Path(mapping['canonical_pointer'])
            assert not target.exists(), target
            with target.open('x') as stream:
                json.dump({**closed, 'tail_registration': reference(args.registration),
                    'actual_worker_pointer': reference(pointer)}, stream)
            linked.append({'case': data['case']['name'], 'pointer': str(target),
                'actual_summary': reference(summary)})
    assert len(linked) == plan['states'] == len({r['case'] for r in linked})
    proof = {'linked_states': len(linked), 'rows': linked, 'registration': reference(args.registration),
        'source_commit': plan['source_commit'], 'interrupted_episodes': 0,
        'scores_or_seeds_changed': False, 'training': False}
    with (args.registration.parent/'link_complete.json').open('x') as stream:
        json.dump(proof, stream, indent=2)
    print(json.dumps({'linked_states': len(linked)}), flush=True)


if __name__ == '__main__':
    main()
