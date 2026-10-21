"""Classify unavailable VLA variants using their saved public catalogs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import pickle
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    from rpent.skill_package.contract import legal_after

    rows = []
    for trial in json.loads(args.audit.read_bytes())['unavailable']:
        ref = trial['endpoint']
        raw = Path(ref['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('saved endpoint changed')
        saved = pickle.loads(raw)
        adapter = saved['public_runtime']['adapter']
        request = adapter['latest_request']
        legal = set(legal_after(request, []))
        required = dict(trial['vla_variant']['parameters'])
        if required.get('mode') != 'task':
            required['mode'] = trial['subtask']['mode']
            for parameter, field in (('anchor_id', 'source_public_id'), ('target_id', 'target_public_id')):
                if trial.get(field) is not None:
                    required[parameter] = trial[field]
        calls = [c for c in request['candidates'] if c['skill'] == 'call_vla']
        exact = [c for c in calls if all(c['parameters'].get(k) == v for k, v in required.items())]
        modes = [c for c in calls if c['parameters']['mode'] == required['mode']]
        ids = {c['id'] for c in exact}
        if trial['binding_missing'] and trial['decisions'] == 1:
            cause = 'binding_missing_early_exit_bypasses_unbound_fallback'
        elif not modes:
            cause = 'requested_mode_not_generated'
        elif not exact:
            cause = 'requested_binding_or_preparation_not_in_catalog'
        elif not ids & legal:
            cause = 'exact_candidate_present_but_not_legal'
        else:
            cause = 'catalog_matches_need_current_binding_trace'
        rows.append({key: trial[key] for key in ('case', 'recovery_budget', 'trial_seed', 'subtask')} |
            {'endpoint': ref, 'classification': cause, 'required_from_logged_binding': required,
             'current_held_id': adapter.get('held'), 'candidate_count': len(request['candidates']),
             'call_vla_count': len(calls), 'requested_mode_count': len(modes),
             'exact_candidates': [{k: c[k] for k in ('id', 'parameters', 'consequences')} for c in exact],
             'legal_exact_ids': sorted(ids & legal),
             'unbound_candidates': [{k: c[k] for k in ('id', 'parameters')} for c in calls
                 if c['id'] in legal and c['parameters']['mode'] in ('task', 'instruction')],
             'anchor_visibility': [{k: anchor.get(k) for k in ('id', 'name', 'visible', 'cached')}
                 for anchor in request['anchors'] if anchor['id'] in (
                     trial.get('source_public_id'), trial.get('target_public_id'))]})
        del saved
    counts = dict(Counter(row['classification'] for row in rows))
    args.output.write_text(json.dumps({'scope': 'saved public catalog, no planner or simulator calls',
        'training': False, 'counts': counts, 'rows': rows}, indent=2)+'\n')
    print(json.dumps({'counts': counts, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
