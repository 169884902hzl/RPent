"""Render the registered stove evaluation requests with C2's current public view."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median
import sys


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--consumer', type=Path, required=True)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert ref(args.input)['sha256'] == args.input_sha256
    sys.path.insert(0, str(args.consumer))
    from robot_decider.bounded_choice.skill_package import SkillPackageBridge
    from robot_decider.bounded_choice.serialization import canonical_json, render_request
    from transformers import AutoTokenizer
    bridge = SkillPackageBridge(args.schema)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
    rows, stats, reasons = [], [], Counter()
    for line, raw in enumerate(args.input.read_bytes().splitlines(), 1):
        source = json.loads(raw)
        assert not source['training_admission'] and source['source_split'] == 'task_holdout'
        public = source['public_request']
        assert hashlib.sha256(canonical_json(public).encode()).hexdigest() == source['public_request_sha256']
        request = bridge.to_model_request(public, compact=True)
        kept = request['questions']['action']['criteria']
        omitted = []
        for candidate in public['candidates']:
            if candidate['id'] in kept:
                assert kept[candidate['id']] == candidate
                continue
            effect = candidate['consequences']
            assert effect['collision'] is True or effect['ik_reachable'] is False
            reason = 'collision' if effect['collision'] is True else 'ik_unreachable'
            reasons[reason] += 1
            omitted.append({'id': candidate['id'], 'reason': reason})
        # Preserve all source/prefix bindings outside the model input. No
        # private labels, snapshots, or acceptable sets enter request.
        before = bridge.to_model_request(public, compact=False)
        before['questions']['action']['criteria'] = {c['id']: c for c in public['candidates']}
        old_text, new_text = render_request(before), render_request(request)
        metrics = {'query_group_id': source['query_group_id'],
            'candidates_before': len(public['candidates']), 'candidates_after': len(kept),
            'rendered_tokens_before': len(tokenizer.encode(old_text, add_special_tokens=False)),
            'rendered_tokens_after': len(tokenizer.encode(new_text, add_special_tokens=False)),
            'rendered_bytes_before': len(old_text.encode()), 'rendered_bytes_after': len(new_text.encode())}
        stats.append(metrics)
        rows.append({'query_group_id': source['query_group_id'], 'source_line': line,
            'source_line_sha256': hashlib.sha256(raw).hexdigest(),
            'source_request_sha256': source['public_request_sha256'],
            'source_state_sha256': source['source_state_sha256'], 'prefix': source['prefix'],
            'private_physical_snapshot': source['private_physical_snapshot'],
            'source_link': source['source_link'], 'record_ids': source['record_ids'],
            'candidate_method_bindings': source['candidate_method_bindings'],
            'omitted_public_blockers': omitted, 'model_request': request,
            'model_request_sha256': hashlib.sha256(canonical_json(request).encode()).hexdigest(),
            'selected_vla_ids_not_retained': [c for c in source['selected_vla_candidate_ids'] if c not in kept],
            'training_admission': False, 'evaluation_only': True})
    assert len(rows) == len({r['query_group_id'] for r in rows}) == 165
    args.output.mkdir(parents=True, exist_ok=False)
    data = args.output/'requests.jsonl'
    data.write_text(''.join(canonical_json(r)+'\n' for r in rows))
    (args.output/'per_request.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in stats))
    report = {'requests': 165, 'input': ref(args.input), 'data': ref(data),
        'physics_roots': len({r['private_physical_snapshot']['sha256'] for r in rows}),
        'schema_contract': bridge.identity, 'consumer': str(args.consumer),
        'tokenizer': str(args.tokenizer), 'token_scope': 'rendered body only; excludes chat wrapper and future output',
        'metrics': {key: {'median': median(r[key] for r in stats), 'max': max(r[key] for r in stats),
            'sum': sum(r[key] for r in stats)} for key in stats[0] if key != 'query_group_id'},
        'omissions': dict(reasons), 'selected_vla_omitted_groups': sum(bool(r['selected_vla_ids_not_retained']) for r in rows),
        'training_admission': False, 'physical_measurements_added': 0,
        'scope': 'public model-view rendering only; original physics roots and ordered prefixes retained; no outcomes transferred or generated'}
    (args.output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
