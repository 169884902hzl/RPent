"""Publish the strictly closed, original-train candidate collection."""
import argparse
import datetime
import fcntl
import hashlib
import json
from pathlib import Path


def reference(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--name', default='C3_DAGGER_PRIORITY1_FINAL_20261024')
    args = parser.parse_args()
    closure = args.closure.resolve()
    manifest_path = closure / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    details_path = closure / 'collection_details.json'
    details = json.loads(details_path.read_bytes())
    for item in (manifest['data'], manifest['replacements'], manifest['query_outcomes']):
        assert reference(item['path']) == item, item
    assert manifest['registered_queries'] == manifest['closed_queries'] == 1963
    assert manifest['pending_queries'] == 0 and manifest['closed_packets'] == 62
    assert manifest['positions'] == manifest['bound_trials'] == 826
    assert manifest['unknown_trials'] == 0 and manifest['unreached_or_unavailable_contexts'] == 1137
    assert manifest['source_split'] == 'train' and manifest['training_admission']
    assert manifest['repeats_each'] == 1 and not manifest['training_executed']
    assert not any(manifest[key] for key in ('PRO', 'D2', 'confirmation'))
    assert sum(details['bound_positions_by_execution_source'].values()) == 826

    root = Path('/public/home/sunyihan/rpent_libero_eval')
    note = {
        'owner': 'Codex3', 'recipient': 'Codex2',
        'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'package': str(closure), 'manifest': reference(manifest_path),
        'report': reference(closure / 'RESULTS.md'),
        'collection_details': reference(details_path),
        'positions': manifest['data'], 'query_outcomes': manifest['query_outcomes'],
        'replacement_mapping': manifest['replacements'],
        'registered_queries': 1963, 'closed_queries': 1963, 'closed_packets': 62,
        'measured_positions': 826, 'known_trials': 826, 'unknown_truth_trials': 0,
        'unreached_or_unavailable_contexts': 1137,
        'positions_by_category': manifest['positions_by_category'],
        'one_trial_outcomes': {
            'self': {
                'trials': sum(row['self'] for row in details['categories'].values()),
                'successes': sum(row['self_success'] for row in details['categories'].values()),
            },
            'vla': {
                'trials': sum(row['vla'] for row in details['categories'].values()),
                'successes': sum(row['vla_success'] for row in details['categories'].values()),
            },
        },
        'query_statuses': manifest['query_statuses'],
        'bound_positions_by_execution_source': details['bound_positions_by_execution_source'],
        'source_queries': manifest['source_queries'],
        'source_split': 'train', 'PRO': False, 'D2': False, 'confirmation': False,
        'training_executed': False, 'collection_repeats': 1,
        'one_trial_is_not_three_trial_acceptability_evidence': True,
        'admission': 'valid bound train rows only; context unknowns are not action failures',
    }
    for owner in ('Codex1', 'Codex2'):
        destination = root / 'coordination/owner_alerts' / owner / f'{args.name}.json'
        with destination.open('x') as stream:
            json.dump(note, stream, indent=2)
    shared = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
    with shared.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write('\n## Codex3 — priority1 DAgger candidate collection closed\n')
        stream.write(json.dumps(note, sort_keys=True) + '\n')
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)
    print(json.dumps(note))


if __name__ == '__main__':
    main()
