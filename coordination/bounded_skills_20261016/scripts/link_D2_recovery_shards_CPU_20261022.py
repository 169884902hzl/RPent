"""Link closed recovery2 shards to their registered forty-case identities."""
import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    full = json.loads((root/'preparation/D2_recovery2.json').read_bytes())
    assert len(full['jobs']) == 40 and not full['training'] and not full['confirmation']
    output = root/'D2_recovery2'
    output.mkdir(exist_ok=True)
    seen, closed = set(), []
    for part in ('a', 'b'):
        plan_path = root/f'preparation/D2_recovery2_{part}.json'
        plan = json.loads(plan_path.read_bytes())
        assert plan['source_commit'] == full['source_commit']
        assert not plan['training'] and not plan['confirmation']
        mapping = plan['parent_case_indices']
        assert len(mapping) == len(plan['jobs']) == 20
        for local, index in enumerate(mapping):
            assert index not in seen and plan['jobs'][local] == full['jobs'][index]
            seen.add(index)
            pointer = root/f'D2_recovery2_{part}/closed_{local:03d}.json'
            if not pointer.exists():
                continue
            saved = json.loads(pointer.read_bytes())
            summary = Path(saved['summary'])
            reference = ref(summary)
            assert saved.get('sha256', reference['sha256']) == reference['sha256']
            result = json.loads(summary.read_bytes())
            assert result['case'] == full['jobs'][index]['case']
            assert result['source_commit'] == full['source_commit']
            assert result.get('full_replay') and type(result['actual_full_replay_success']) is bool
            value = {'summary': str(summary), 'sha256': reference['sha256'],
                'registered_case_index': index, 'shard_pointer': ref(pointer)}
            target = output/f'closed_{index:03d}.json'
            if target.exists():
                assert json.loads(target.read_bytes()) == value
            else:
                with target.open('x') as stream:
                    json.dump(value, stream, indent=2)
            closed.append(index)
    assert seen == set(range(40))
    print(json.dumps({'root': str(root), 'linked': len(closed),
        'missing_indices': sorted(set(range(40))-set(closed)),
        'source_commit': full['source_commit'], 'physics_steps': 0, 'training': False}))


if __name__ == '__main__':
    main()
