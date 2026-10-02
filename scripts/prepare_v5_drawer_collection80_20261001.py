# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Prepare original Spatial4 only after a complete five-init physical qualification."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from scripts.prepare_v5_original_counterfactuals_20261001 import rewrites


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from libero.libero import benchmark
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--qualification', type=Path, required=True)
    args = parser.parse_args()
    proof = json.loads(args.qualification.read_text())
    episodes = proof['episodes']
    assert len(episodes) == 5 and {r['init'] for r in episodes} == set(range(5))
    assert all(r['result']['suite'] == 'libero_spatial' and r['result']['task'] == 4
               and r['returncode'] == 0 for r in episodes)
    correct = sum(r['result'].get('correct_finish', False) for r in episodes)
    if correct < 4:
        raise ValueError(f'original Spatial4 not qualified: {correct}/5 correct finish')
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    original = root / 'source_v5_collect_receipt51_20261001'
    # This task was excluded from all previously registered original collectors.
    for part in range(22):
        p = root / 'source_v5_original_training1_retry1_20261001/configs/original_training1_registered_parts_v2_20261001' / f'part_{part}.json'
        assert not any(e['suite'] == 'libero_spatial' and e['task'] == 4
                       for e in json.loads(p.read_text())['episodes'])
    for part in range(6):
        p = original / f'configs/qualified_collection48_parts_20261001/part_{part}.json'
        assert not any(e['suite'] == 'libero_spatial' and e['task'] == 4
                       for e in json.loads(p.read_text())['episodes'])
    task = benchmark.get_benchmark_dict()['libero_spatial']().get_task(4)
    language = task.language
    match = re.fullmatch(r'pick up the (.+) and place it (in|on) the (.+)', language)
    if match is None:
        raise ValueError('unregistered original instruction grammar')
    sentences = rewrites(match[1], match[3], match[2])
    assert len(sentences) == len(set(sentences)) == 30
    prepared = args.source / 'configs/drawer_collection80_20261001'
    prepared.mkdir(exist_ok=False)
    evidence = prepared / 'qualification5.json'
    evidence.write_bytes(args.qualification.read_bytes())
    bank = prepared / 'wording_bank30.json'
    bank.write_text(json.dumps({'tasks': {'libero_spatial/4': {
        'suite': 'libero_spatial', 'task': 4, 'instruction': language,
        'instruction_sha256': hashlib.sha256(language.encode()).hexdigest(), 'rewrites': sentences}}}, indent=2) + '\n')
    config = json.loads((original / 'configs/qualified_collection48_config_20261001.json').read_text())
    config['eligible_tasks'] = [['libero_spatial', 4]]
    config['wording_bank'] = str(bank)
    config['wording_bank_sha256'] = sha(bank)
    config['shared_schema'] = str(args.source / 'shared_v5r_schema.py')
    assert sha(Path(config['shared_schema'])) == config['shared_schema_sha256']
    config_path = prepared / 'collection_config.json'
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    budget = json.loads((original / 'configs/qualified_collection48_parts_20261001/part_0.json').read_text())['budget']
    states = benchmark.get_benchmark_dict()['libero_spatial']().get_task_init_states(4)
    training = [{'suite': 'libero_spatial', 'task': 4, 'seed': init,
                 'init_state_sha256': hashlib.sha256(np.asarray(states[init]).tobytes(order='C')).hexdigest()}
                for init in range(10, 40)]
    plans = []
    for name, subset in (('smoke', training[:1]), ('remaining', training[1:])):
        p = prepared / f'{name}.json'
        p.write_text(json.dumps({'purpose': 'newly qualified original drawer task collection; no PRO inputs',
                                'libero_type': 'standard', 'budget': budget, 'episodes': subset}, indent=2) + '\n')
        plans.append({'part': name, 'path': str(p), 'sha256': sha(p), 'episodes': len(subset)})
    manifest = {'purpose': 'original Spatial4 training collection; not full200 or SFT admission',
                'qualification': str(evidence), 'qualification_sha256': sha(evidence), 'expert_correct5': correct,
                'plans': plans, 'collection_config': str(config_path), 'collection_config_sha256': sha(config_path),
                'wording_bank_sha256': sha(bank), 'different_instructions': 30,
                'training_init_indices': list(range(10, 40)), 'excluded_init_indices': list(range(10)) + [40],
                'reserved_episode_overlap': 0, 'PRO_inputs_used': False, 'state_source': 'perception',
                'private_truth': 'labels_only', 'generator_sha256': sha(Path(__file__))}
    output = prepared / 'manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(output), 'sha256': sha(output), 'expert_correct5': correct, 'plans': plans}))


if __name__ == '__main__':
    main()
