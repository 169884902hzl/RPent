"""Register explicit eligible original-task training init states and shards."""

import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    from libero.libero import benchmark

    root = Path('/public/home/sunyihan/rpent_libero_eval')
    source = root / 'source_v5_original_training1_20261001'
    registry_path = root / 'configs/eligible_original_tasks2822_20261001.json'
    registry = json.loads(registry_path.read_text())
    part_dir = source / 'configs/original_training1_parts_20261001'
    part_dir.mkdir(exist_ok=False)
    budget = {'max_decisions': 100, 'max_chunks': 80, 'max_episode_steps': 10000, 'prompt_limit': 3072}
    manifests, all_episodes = [], []
    for index, task in enumerate(registry['tasks']):
        if task['correct5'] < 4:
            raise ValueError('noneligible task in original collection')
        suite = benchmark.get_benchmark_dict()[task['suite']]()
        states = suite.get_task_init_states(task['task'])
        if len(states) < 40:
            raise ValueError('original task lacks registered training states')
        episodes = []
        for init_index in range(10, 40):
            vector = np.asarray(states[init_index])
            episodes.append({'suite': task['suite'], 'task': task['task'], 'seed': init_index,
                             'init_state_sha256': hashlib.sha256(vector.tobytes(order='C')).hexdigest()})
        plan = {'purpose': 'original training collection init10-39 no PRO inputs', 'libero_type': 'standard',
                'budget': budget, 'episodes': episodes}
        path = part_dir / f'part_{index}.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        manifests.append({'part': index, 'path': str(path), 'episodes': len(episodes),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'suite': task['suite'], 'task_id': task['task']})
        all_episodes.extend(episodes)
    smoke = next(e for e in all_episodes if e['suite'] == 'libero_spatial' and e['task'] == 0 and e['seed'] == 10)
    (source / 'configs/v5_original_training1_smoke_20261001.json').write_text(json.dumps({
        'purpose': 'first actual original training episode physics/request verification',
        'libero_type': 'standard', 'budget': budget, 'episodes': [smoke]}, indent=2) + '\n')
    index = {'purpose': 'registered original data shards, not yet completed or admitted',
             'episodes': len(all_episodes), 'tasks': len(registry['tasks']), 'wordings_per_task': 30,
             'registry_path': str(registry_path), 'registry_sha256': hashlib.sha256(registry_path.read_bytes()).hexdigest(),
             'parts': manifests, 'excluded_init_indices': list(range(10)) + [40],
             'training_init_indices': list(range(10, 40)),
             'counterfactual_rules': json.loads((source / 'configs/v5_original_training1_collection_20261001.json').read_text())['counterfactual_rules'],
             'counterfactual_status': 'registered; first660 collect original goals, counterfactual goals follow separately'}
    (source / 'configs/original_training1_index_20261001.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({k: v for k, v in index.items() if k != 'parts'}))


if __name__ == '__main__':
    main()
