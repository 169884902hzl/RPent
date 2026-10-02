# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register only the failed original milk episodes for a versioned repair replay."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    old = root / 'source_v5_collect_receipt51_20261001'
    ledger = root / 'results/harness_v5/qualified_original_training48_20261001/job2905_task2/episodes.jsonl'
    original = old / 'configs/qualified_collection48_parts_20261001/part_2.json'
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(records) == 30
    assert {(r['episode']['suite'], r['episode']['task'], r['episode']['seed'])
            for r in records} == {('libero_object', 7, s) for s in range(10, 40)}
    failed = [r['episode'] for r in records if not r['result'].get('correct_finish')]
    assert len(failed) == 26 and failed[0]['seed'] == 10
    original_plan = json.loads(original.read_text())
    assert original_plan['libero_type'] == 'standard'
    assert original_plan['episodes'] == [r['episode'] for r in records]
    config = json.loads((old / 'configs/qualified_collection48_config_20261001.json').read_text())
    bank = Path(config['wording_bank'])
    assert sha(bank) == config['wording_bank_sha256']
    prepared = args.source / 'configs/milk_replay75_20261001'
    prepared.mkdir(exist_ok=False)
    copied_bank = prepared / 'registered_wording_bank.json'
    copied_bank.write_bytes(bank.read_bytes())
    config['wording_bank'] = str(copied_bank)
    config['shared_schema'] = str(args.source / 'shared_v5r_schema.py')
    assert sha(Path(config['shared_schema'])) == config['shared_schema_sha256']
    config['collection_attempt'] = 'milk71_repair_v1'
    config['replay_of'] = {'episode_ledger': str(ledger), 'sha256': sha(ledger),
                           'job_id': '2905_2', 'reason': 'missing milk due to segmentation category collision'}
    config_path = prepared / 'collection_config.json'
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    plans = []
    for name, episodes in (('smoke', failed[:1]), ('remaining', failed[1:])):
        plan = copy.deepcopy(original_plan)
        plan['purpose'] = 'original training milk repair replay; old failures preserved; not new independent initial states'
        plan['episodes'] = episodes
        path = prepared / f'{name}.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        plans.append({'part': name, 'path': str(path), 'sha256': sha(path), 'episodes': len(episodes)})
    manifest = {'purpose': 'versioned repair replay; not SFT admission', 'source': str(args.source),
                'original_ledger': str(ledger), 'original_ledger_sha256': sha(ledger),
                'original_plan': str(original), 'original_plan_sha256': sha(original),
                'preserved_successful_old_episodes': 4, 'replayed_failed_episodes': len(failed),
                'new_independent_initial_states': 0, 'collection_attempt': config['collection_attempt'],
                'collection_config': str(config_path), 'collection_config_sha256': sha(config_path),
                'shared_schema_sha256': config['shared_schema_sha256'],
                'wording_bank_sha256': sha(copied_bank), 'plans': plans,
                'training_init_indices': [e['seed'] for e in failed],
                'PRO_inputs_used': False, 'private_truth': 'labels_only', 'state_source': 'perception',
                'original_expert_qualification': '2887 original Object7 5/5 correct finish',
                'generator_sha256': sha(Path(__file__))}
    output = prepared / 'manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(output), 'sha256': sha(output), 'plans': plans}))


if __name__ == '__main__':
    main()
