"""Compare old/new prompt text on the six registered saved handoff starts."""

import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_subtasks import pi05_instance_description, subtask_phrase

    rows = []
    for row in json.loads(args.registry.read_bytes())['rows']:
        saved = pickle.loads(Path(row['branchpoint']).read_bytes())
        old = json.loads(Path(row['raw_summary']).read_bytes())
        runtime = saved['public_runtime']
        adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
        vars(adapter).update(runtime['adapter'])
        adapter.scene = SimpleNamespace(**runtime['scene'])
        request = saved['request']
        candidate = next(c for c in request['candidates']
            if c['id'] == old['selected_candidate_id'])
        params = candidate['parameters']
        source = adapter.scene.entities[params['anchor_id']]
        name = pi05_instance_description(source, adapter.scene.entities, adapter.scene.view_axes)
        target = adapter.scene.entities.get(params.get('target_id'))
        target_name = (pi05_instance_description(target, adapter.scene.entities, adapter.scene.view_axes)
            if target is not None else None)
        before = ('pick up the '+name if params['mode'] == 'pick'
            else subtask_phrase(name, params['mode'], target_name))
        after, _ = adapter._vla_prompt(params)
        rows.append({'seed': row['seed'], 'branchpoint': ref(row['branchpoint']),
            'selected_candidate_id': candidate['id'], 'parameters': params,
            'old_prompt': before, 'new_prompt': after,
            'prompt_bytes_equal': before.encode() == after.encode()})
    report = {'source': str(args.source), 'registry': ref(args.registry), 'script': ref(__file__),
        'rows': rows, 'all_six_prompt_bytes_equal': len(rows) == 6 and all(
            r['prompt_bytes_equal'] for r in rows),
        'physics_steps': 0, 'sam_calls': 0, 'vla_calls': 0, 'training': False,
        'scope': 'prompt rendering only; not a policy-action or physical outcome comparison'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
