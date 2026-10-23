"""Bind completed redistributed workers to their unchanged canonical case slots."""
import argparse
import hashlib
import json
from pathlib import Path


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    prep = args.run/'preparation'
    complete = json.loads((prep/'redistribution4_drain_complete.json').read_bytes())
    assert complete['interrupted_episodes'] == 0
    registration = prep/'redistribution4_submissions.json'
    plan = json.loads(registration.read_bytes())
    linked = []
    for shard in plan['rows']:
        panel_path = Path(shard['manifest']['path'])
        assert reference(panel_path) == shard['manifest']
        panel = json.loads(panel_path.read_bytes())
        for index, mapping in enumerate(shard['mapping']):
            pointer = Path(shard['output'])/f'closed_{index:03d}.json'
            closed = json.loads(pointer.read_bytes())
            summary = Path(closed['summary'])
            assert reference(summary)['sha256'] == closed['sha256']
            data = json.loads(summary.read_bytes())
            assert data['case'] == panel['jobs'][index]['case'] == mapping['job']['case']
            assert data['source_commit'] == plan['source_commit']
            assert data['restored_original_subtask_start']['same_captured_physics']
            canonical = args.run/f'formal155_shard{mapping["canonical_shard"]}'/f'closed_{mapping["canonical_index"]:03d}.json'
            assert not canonical.exists(), canonical
            with canonical.open('x') as stream:
                json.dump({**closed, 'redistribution': reference(registration),
                    'physical_worker_pointer': reference(pointer)}, stream)
            linked.append({'case': data['case']['name'], 'canonical_pointer': str(canonical),
                'actual_summary': reference(summary)})
    assert len(linked) == plan['unstarted_cases']
    assert len({r['case'] for r in linked}) == len(linked)
    proof = {'launch_only': True, 'training': False, 'linked_newly_completed_cases': len(linked),
        'original_completed_cases_preserved': complete['completed_episodes_preserved'],
        'source_commit': plan['source_commit'], 'rows': linked,
        'new_physical_trials_not_replayed_or_rescored': True}
    with (prep/'redistribution4_link_complete.json').open('x') as stream:
        json.dump(proof, stream, indent=2)
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()
