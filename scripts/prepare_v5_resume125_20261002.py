# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Resume only the explicitly unattempted Long3/Long5 training episodes."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ('prior-plan', 'prior-ledger', 'base-config', 'source', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    prior = json.loads(a.prior_plan.read_text())
    attempted = [json.loads(x)['episode'] for x in a.prior_ledger.read_text().splitlines()]
    identity = lambda e: (e['suite'], e['task'], e['seed'])
    seen = {identity(e) for e in attempted}
    assert len(seen) == len(attempted) == 24
    remaining = [e for e in prior['episodes'] if identity(e) not in seen]
    assert len(remaining) == 34 and not seen.intersection(map(identity, remaining))
    assert all(e['suite'] == 'libero_10' and e['task'] in (3,5) and 10 <= e['seed'] < 40 for e in remaining)
    a.output.mkdir(parents=True, exist_ok=False)
    budget = {**prior['budget'], 'termination_accounting_v2': True,
              'candidate_failure_counts_v1': True, 'furniture_parts_v1': True,
              'articulate_verification_v1': True, 'fixture_support_filter_v1': True,
              'target_cache_v1': True, 'strict_place_v1': True, 'adjust_place_v1': True}
    plans = {}
    for name, episodes in [('smoke', [{'suite':'libero_10','task':t,'seed':10} for t in (3,5)]), ('remaining', remaining)]:
        path = a.output / (name + '.json')
        path.write_text(json.dumps({'purpose': 'Original bool-receipt repair validation' if name == 'smoke' else 'Resume only 34 unattempted registered original training episodes',
                                   'libero_type':'standard', 'budget':budget, 'episodes':episodes,
                                   'source_commit':'e505221'}, indent=2) + '\n')
        plans[name] = {'path':str(path.resolve()),'sha256':sha(path),'episodes':len(episodes)}
    config = json.loads(a.base_config.read_text())
    assert sha(config['wording_bank']) == config['wording_bank_sha256']
    assert sha(a.source/'shared_v5r_schema.py') == config['shared_schema_sha256']
    config['shared_schema'] = str(a.source/'shared_v5r_schema.py')
    config['exclusions']['development_init_indices'] = [0,1,2,3,4,40,41]
    path = a.output/'collection_config.json'
    path.write_text(json.dumps(config,indent=2)+'\n')
    report = {'prior_plan':{'path':str(a.prior_plan),'sha256':sha(a.prior_plan)},
              'prior_ledger':{'path':str(a.prior_ledger),'sha256':sha(a.prior_ledger)},
              'plans':plans,'previously_attempted':24,'remaining_episodes':34,
              'repeat_attempted_episodes':0,'original_smoke_writes_training_rows':False,
              'collection_config':{'path':str(path),'sha256':sha(path)},
              'source':str(a.source),'generator_sha256':sha(__file__)}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
