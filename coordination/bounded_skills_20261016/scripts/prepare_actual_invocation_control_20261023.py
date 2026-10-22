"""Repeat the old actual in-place calls, not their nominal initial-pose name."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(data, stream, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    run = base/'option_ceiling_20261022/regression155_f6987f0d'
    plan = json.loads((run/'preparation/original90_manifest.json').read_bytes())
    before = {}
    for line in (base/'qualified90_9716b68c/CPU_closed90_r1/positions.jsonl').open():
        row = json.loads(line)
        before[row['case']['name']] = json.loads(Path(row['source']['path']).read_bytes())['result']
    after = {}
    for pointer in run.glob('shard*/closed_*.json'):
        entry = json.loads(pointer.read_bytes())
        path = Path(entry['summary'])
        assert ref(path)['sha256'] == entry['sha256']
        row = json.loads(path.read_bytes())
        after[row['case']['name']] = row
    revision = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())
    selected, provenance = [], []
    for case in plan['cases']:
        name = case['name']
        old, new = before[name]['trials'][0], after[name]['trials'][0]
        assert old['request_sha256'] == new['request_sha256']
        if old.get('selected_candidate_id') == new.get('selected_candidate_id'):
            continue
        if old.get('selected_candidate_id') is None:
            # An old unavailable option has no actual invocation to repeat.
            continue
        with Path(old['choices']['path']).open() as stream:
            first = json.loads(next(stream))
        candidate = next(c for c in first['request']['candidates'] if c['id'] == old['selected_candidate_id'])
        assert candidate['skill'] == 'call_vla'
        assert candidate['parameters'].get('preparation') == 'in_place'
        current = copy.deepcopy(case)
        current['diagnostic'].update(include_self=False,
            vla_variants=[{'name': 'old_actual_in_place', 'parameters': {'preparation': 'in_place'}}])
        selected.append(current)
        provenance.append({'case': name, 'old_actual_candidate': candidate,
            'old_trials': before[name]['trials'], 'new_requested_trials': after[name]['trials'],
            'scope': 'same complete physics/request and trial seeds; control for changed actual invocation'})
    assert selected
    plan.update(source_commit=revision['commit'], cases=selected)
    out = base/'option_ceiling_20261022/actual_invocation_control'
    manifest = out/'preparation/manifest.json'
    write(manifest, plan)
    parent = json.loads((run/'preparation/all155.json').read_bytes())
    parent.update(source=str(args.source), source_commit=revision['commit'],
        jobs=[{'kind': 'original_fork', 'case': c, 'manifest': ref(manifest)} for c in selected])
    write(out/'preparation/jobs.json', parent)
    write(out/'preparation/provenance.json', {'rows': provenance, 'states': len(selected),
        'training': False, 'PRO': False, 'D2': False, 'confirmation': False})
    print(json.dumps({'output': str(out), 'states': len(selected), 'trials': 3*len(selected)}))


if __name__ == '__main__':
    main()
