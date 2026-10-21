"""Register all three original-cup trials for a same-state/seed hold replay."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--original-manifest', type=Path, required=True)
    p.add_argument('--original-results', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.source = a.source.resolve(strict=True)
    sys.path.insert(0, str(a.source))
    from scripts.bounded_state_exclusions import check_exclusions
    from scripts.probe_bounded_hybrid_repair import validate_plan

    original = json.loads(a.original_manifest.read_bytes())
    case = next(c for c in original['cases'] if c['category'] == 'cup_transfer')
    matches = [f for f in a.original_results.glob('job*/N8/*/worker_summary.json')
               if json.loads(f.read_bytes())['case'] == case]
    if len(matches) != 1:
        raise ValueError('one closed original cup worker required')
    result = json.loads(matches[0].read_bytes())['result']
    if result['status'] != 'physical_result':
        raise ValueError('original outcome cohort has not closed')
    trials = [t for t in result['trials'] if t['method'] == 'call_vla']
    if len(trials) != 3:
        raise ValueError('all three original policy trials are required')
    start = matches[0].parent / case['name'] / 'private_branchpoint.pkl'
    root = start.parent
    cases = []
    for index, trial in enumerate(trials, 1):
        clone = copy.deepcopy(case)
        clone['name'] += '_hold_replay_' + str(index)
        clone['original_case_name'] = case['name']
        clone['diagnostic'] = {**clone['diagnostic'], 'kind': 'replay',
            'old_summary': ref(root / f'call_vla_{index}/summary.json'),
            'branchpoint': ref(start)}
        check_exclusions([clone], original['permanent_exclusions'])
        cases.append(clone)
    revision = json.loads((a.source / 'SOURCE_REVISION.json').read_bytes())['commit']
    plan = {'evaluation': 'hybrid_repair', 'source_commit': revision,
            'training': False, 'confirmation': False, 'cases': cases,
            'schema6_source': False,
            'catalog_scope': 'same published schema6 catalog; no header migration or request reconstruction',
            'selection': 'all three cup seeds, including private failure; old records retained',
            'baseline_source_commit': original['source_commit'],
            'original_manifest': ref(a.original_manifest),
            'permanent_exclusions': original['permanent_exclusions'],
            'scope': 'development replay of hold verification and first bounded continuation; not new confirmation'}
    validate_plan(plan)
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = a.output / 'manifest.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    batch = {'domain': 'original', 'source': str(a.source), 'source_commit': revision,
             'manifest': ref(manifest)}
    for name, indices in (('startup', [0]), ('formal', [0, 1, 2])):
        data = {'selected_n': 3, 'batches': [{**batch, 'indices': indices}],
                'training': False, 'confirmation': False,
                'sam3_entry': original.get('sam3_entry')}
        # The source-owned equivalent feature-cache entry is independently pinned.
        entry = a.source.parent / 'sam3_feature_cache_startup_20261020.py'
        data['sam3_entry'] = ref(entry)
        (a.output / (name + '_plan.json')).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'manifest': ref(manifest), 'source_commit': revision}))


if __name__ == '__main__':
    main()
