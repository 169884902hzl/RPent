# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register failed original table-centre training episodes for versioned recovery."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from libero.libero import benchmark

    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--prior-episodes', type=Path, required=True)
    p.add_argument('--expert-ledger', type=Path, required=True)
    p.add_argument('--base-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    expert = [json.loads(s) for s in args.expert_ledger.read_text().splitlines()]
    assert len(expert) == 5
    assert {(r['episode']['suite'], r['episode']['task'], r['episode']['seed']) for r in expert} == {
        ('libero_spatial', 2, i) for i in range(5)}
    assert sum(bool(r['result'].get('correct_finish')) for r in expert) >= 4
    prior = [r for r in json.loads(args.prior_episodes.read_text()) if r['identity'][:2] == ['libero_spatial', 2]]
    assert len(prior) == 30 and {r['identity'][2] for r in prior} == set(range(10, 40))
    failed = sorted((r for r in prior if not r['result'].get('correct_finish')), key=lambda r: r['identity'][2])
    if not failed:
        raise ValueError('no failed training episodes to replay')
    states = benchmark.get_benchmark_dict()['libero_spatial']().get_task_init_states(2)
    episodes = [{'suite': 'libero_spatial', 'task': 2, 'seed': r['identity'][2],
                 'init_state_sha256': hashlib.sha256(np.asarray(states[r['identity'][2]]).tobytes(order='C')).hexdigest()}
                for r in failed]
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.base_config.read_text())
    bank = Path(config['wording_bank'])
    assert sha(bank) == config['wording_bank_sha256']
    copied = args.output / 'wording_bank.json'
    copied.write_bytes(bank.read_bytes())
    config.update(wording_bank=str(copied), shared_schema=str(args.source / 'shared_v5r_schema.py'),
                  eligible_tasks=[['libero_spatial', 2]], split='train',
                  collection_attempt='table_measurement_replay99_v1',
                  replay_of={'prior_episodes': str(args.prior_episodes), 'sha256': sha(args.prior_episodes),
                             'reason': 'table-centre source binding and transfer rewrite repair'})
    assert sha(config['shared_schema']) == config['shared_schema_sha256']
    cfg = args.output / 'collection_config.json'
    cfg.write_text(json.dumps(config, indent=2) + '\n')
    plans = []
    for name, subset in [('smoke', episodes[:1]), ('remaining', episodes[1:])]:
        path = args.output / f'{name}.json'
        path.write_text(json.dumps({'purpose': 'versioned training table-centre recovery; not new independent init states',
            'libero_type': 'standard', 'budget': {'max_decisions': 100, 'max_chunks': 80,
            'max_episode_steps': 10000, 'prompt_limit': 3072}, 'episodes': subset}, indent=2) + '\n')
        plans.append({'part': name, 'path': str(path), 'sha256': sha(path), 'episodes': len(subset)})
    report = {'purpose': 'registered original training repair; not SFT admission',
              'source': str(args.source), 'prior_episodes': str(args.prior_episodes),
              'prior_episodes_sha256': sha(args.prior_episodes), 'expert_ledger': str(args.expert_ledger),
              'expert_ledger_sha256': sha(args.expert_ledger),
              'expert_correct5': sum(bool(r['result'].get('correct_finish')) for r in expert),
              'preserved_successful_old_episodes': len(prior) - len(failed),
              'replayed_failed_episodes': len(failed), 'new_independent_init_states': 0,
              'collection_attempt': config['collection_attempt'], 'plans': plans,
              'collection_config': str(cfg), 'collection_config_sha256': sha(cfg),
              'wording_bank_sha256': sha(copied), 'training_init_indices': [e['seed'] for e in episodes],
              'excluded_init_indices': list(range(10)) + [40], 'PRO_inputs_used': False,
              'state_source': 'perception', 'truth_usage': 'labels_only', 'generator_sha256': sha(__file__)}
    path = args.output / 'registration.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'registration': str(path), 'sha256': sha(path), 'plans': plans}))


if __name__ == '__main__':
    main()
