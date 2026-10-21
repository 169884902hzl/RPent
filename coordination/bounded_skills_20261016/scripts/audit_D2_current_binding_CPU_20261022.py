"""Complete unavailable-call attribution using each saved public binding state."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from robots.libero.v5_oracle_policy import OriginalOraclePolicy
    from scripts.probe_bounded_hybrid_d2 import bind_subtask, unbound_vla_candidate
    from rpent.skill_package.contract import legal_after
    report = json.loads(args.catalog.read_bytes())
    rows = []
    for prior in report['rows']:
        row = dict(prior)
        if row['classification'] == 'binding_missing_early_exit_bypasses_unbound_fallback':
            row['resolved_classification'] = row['classification']
            rows.append(row)
            continue
        raw = Path(row['endpoint']['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['endpoint']['sha256']:
            raise ValueError('endpoint changed')
        runtime = pickle.loads(raw)['public_runtime']
        request = runtime['adapter']['latest_request']
        adapter = SimpleNamespace(scene=SimpleNamespace(**runtime['scene']),
            ex=SimpleNamespace(instruction=request['instruction']))
        binding = OriginalOraclePolicy(None)
        vars(binding).update(runtime['binding'])
        source, target = bind_subtask(SimpleNamespace(binding=binding), adapter, row['subtask'])
        required = dict(row['required_from_logged_binding'])
        missing = source is None or bool(row['subtask']['target_symbol']) and target is None
        if required['mode'] != 'task':
            if source is not None:
                required['anchor_id'] = source.id
            if target is not None:
                required['target_id'] = target.id
        legal = set(legal_after(request, []))
        calls = [c for c in request['candidates'] if c['skill'] == 'call_vla']
        exact = [c for c in calls if c['id'] in legal
            and all(c['parameters'].get(k) == v for k, v in required.items())]
        if all(c['skill'] in {'finish', 'ask_help'} for c in request['candidates']):
            cause = 'public_progress_termination_removed_all_action_candidates'
        elif missing:
            cause = 'binding_lost_after_executed_recovery_bypasses_unbound_fallback'
        elif required['mode'] in {'on', 'in'} and runtime['adapter'].get('held') is None:
            cause = 'placement_mode_requires_public_held_identity'
        elif not any(c['parameters']['mode'] == required['mode'] for c in calls):
            cause = 'bound_public_category_does_not_generate_requested_mode'
        elif not exact:
            cause = 'current_binding_or_variant_not_in_catalog'
        else:
            cause = 'exact_current_candidate_present_unresolved'
        fallback = unbound_vla_candidate(request, request['instruction'], row['subtask']['mode'])
        row.update(resolved_classification=cause,
            current_source_id=source.id if source else None, current_target_id=target.id if target else None,
            current_binding_missing=missing, current_required=required,
            public_source_category=source.name if source else None,
            public_target_category=target.name if target else None,
            progress=request.get('progress'),
            available_modes=sorted({c['parameters']['mode'] for c in calls}),
            legal_current_exact=[c['id'] for c in exact],
            legal_unbound_fallback=None if fallback is None else
                {k: fallback[k] for k in ('id', 'parameters')})
        rows.append(row)
        del runtime
    result = {'scope': 'saved public entities and bindings only; no planning, RPC, or simulation',
        'training': False, 'source': str(args.source), 'input': str(args.catalog),
        'input_sha256': hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        'counts': dict(Counter(r['resolved_classification'] for r in rows)), 'rows': rows}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'counts': result['counts'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
