"""Register original train snapshots and three measured B2 invocation variants."""
import argparse
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import sys


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--default-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-category', type=int, default=10)
    parser.add_argument('--self-repeats', type=int, default=1)
    args = parser.parse_args()
    args.source = args.source.resolve(strict=True)
    sys.path.insert(0, str(args.source))
    from robots.libero.bounded_offline_labels import load_annotation_state
    from robots.libero.bounded_hybrid_diagnostic import split_subtasks
    from scripts.bounded_state_exclusions import check_exclusions
    from scripts.probe_bounded_hybrid_repair import validate_plan

    default = json.loads(args.default_manifest.read_bytes())
    index_ref = default['frozen_parent_index']
    assert ref(index_ref['path']) == index_ref
    parents = json.loads(Path(index_ref['path']).read_bytes())['parents']
    cohort_ref = default['original_cohort']
    assert ref(cohort_ref['path']) == cohort_ref
    cohort = json.loads(Path(cohort_ref['path']).read_bytes())
    cases = {case['name']: case for case in cohort['cases']}
    calibration = default['cases'][0]['grasp_measurement_calibration']
    groups = defaultdict(list)
    for parent_id, parent in parents.items():
        case = cases[parent['episode_id']]
        if parent['split'] == 'train' and parent['status'] == 'ok':
            groups[case['category']].append((parent_id, parent))
    order = ['bowl_transfer', 'box_transfer', 'cup_transfer', 'container',
        'drawer_open', 'drawer_close', 'microwave_open', 'microwave_close', 'plate_push']
    variants = [
        {'name': 'in_place', 'parameters': {'preparation': 'in_place'}},
        {'name': 'initial_pose', 'parameters': {'preparation': 'initial_pose'}},
        {'name': 'full_task', 'parameters': {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'}},
    ]
    minimum_remaining = default['cases'][0]['diagnostic']['budget']['max_controls']
    selected, coverage, lines = [], {}, {}
    for category in order:
        ordered = sorted(groups[category], key=lambda row: (row[1]['episode_id'], row[1]['source_link']['line']))
        wanted, loaded = [], {}
        used_snapshots, used_initial = set(), set()
        # Prefer actual held states, then later nonterminal intermediate
        # positions. Outcomes of the newly registered branches are unseen.
        # Source row identities avoid decompressing unselectable snapshots.
        for phase_pool, quota in [('held', args.per_category//2),
                ('middle', args.per_category//2), ('all', args.per_category)]:
            pool = (sorted(ordered, key=lambda row: (row[1]['episode_id'], -row[1]['source_link']['line']))
                    if phase_pool == 'middle' else ordered)
            for parent_id, parent in pool:
                if len(wanted) >= quota:
                    break
                if parent['state_sha256'] in used_snapshots or parent['initial_state_sha256'] in used_initial:
                    continue
                link = parent['source_link']
                if link['path'] not in lines:
                    assert ref(link['path'])['sha256'] == link['sha256']
                    lines[link['path']] = Path(link['path']).read_text().splitlines()
                row = json.loads(lines[link['path']][link['line']-1])
                if row['request']['remaining_sim_steps'] < minimum_remaining:
                    continue
                if phase_pool == 'held' and row['request']['robot']['held_anchor_id'] is None:
                    continue
                if phase_pool == 'middle' and row['index'] == 0:
                    continue
                if parent_id not in loaded:
                    annotation = parent['private_prefix_annotation_state']
                    saved = load_annotation_state(annotation['path'], annotation['sha256'])
                    status, old = saved['private_status'], saved['adapter']
                    goal_index = next((i for i, value in enumerate(status['satisfied']) if not value), None)
                    specs = [] if goal_index is None else split_subtasks(status['goals'], old.ex.instruction)[0]
                    specs = [spec for spec in specs if spec['goal_index'] == goal_index]
                    source = (saved['binding'].get('_bindings', {}).get(status['goals'][goal_index][1])
                              if goal_index is not None else None)
                    held = old.held is not None and old.held == source
                    mode = (next((spec['mode'] for spec in specs if spec['mode'] != 'pick'), None)
                            if held else specs[0]['mode'] if specs else None)
                    phase = 'held' if held else 'initial' if row['index'] == 0 else 'intermediate'
                    loaded[parent_id] = (goal_index, mode, phase)
                goal_index, mode, phase = loaded[parent_id]
                if (mode is None or (phase_pool == 'middle' and phase == 'initial')
                        or (phase_pool == 'held' and phase != 'held')):
                    continue
                assert row['private_pre_execution_snapshot']['sha256'] == parent['state_sha256']
                wanted.append((parent_id, parent, row, goal_index, mode, phase))
                used_snapshots.add(parent['state_sha256'])
                used_initial.add(parent['initial_state_sha256'])
        coverage[category] = {'selected': len(wanted), 'registered_parent_states': len(ordered),
            'loaded_eligibility_states': len(loaded), 'unique_initial_states': len(used_initial),
            'phases': {phase: sum(value[-1] == phase for value in wanted) for phase in ('initial', 'intermediate', 'held')}}
        print(json.dumps({'registered_category': category, **coverage[category]}), flush=True)
        if len(wanted) < args.per_category:
            raise ValueError(f'{category}: only {len(wanted)} distinct train initial states available')
        for parent_id, parent, row, goal_index, mode, phase in wanted:
            case = copy.deepcopy(cases[parent['episode_id']])
            case['name'] += f'_B2_d{row["index"]:03d}'
            case['grasp_measurement_calibration'] = calibration
            case['source_training_parent_ids'] = [parent_id]
            case['diagnostic'] = {'kind': 'original_fork', 'domain': 'original',
                'subtask_mode': mode, 'goal_index': goal_index,
                'original_subtask_start': {'physics': row['private_pre_execution_snapshot'],
                    'annotation': parent['private_prefix_annotation_state'], 'decision_index': row['index']},
                'trial_seed_base': 30200000+len(selected)*10000, 'include_self': True,
                'self_repeats': args.self_repeats,
                'targeted_vla_measurement_v1': True, 'vla_variants': variants,
                'budget': default['cases'][0]['diagnostic']['budget']}
            case['saved_start_phase'] = phase
            selected.append(case)
    check_exclusions(selected, default['permanent_exclusions'])
    revision = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())['commit']
    plan = {'evaluation': 'hybrid_repair', 'source_commit': revision, 'training': False,
        'confirmation': False, 'vla_options_v2': True, 'schema6_source': True,
        'cases': selected, 'permanent_exclusions': default['permanent_exclusions'],
        'frozen_parent_index': index_ref, 'original_cohort': cohort_ref,
        'selection': 'train+ok only; prefer held then later intermediate; enough remaining public budget for max_controls; deterministic identity order, no new outcomes; distinct initial identities within category',
        'minimum_remaining_sim_steps': minimum_remaining,
        'registration_generator': ref(__file__), 'coverage': coverage, 'missing_categories': ['stove_on', 'stove_off'],
        'missing_reason': 'both stove tasks are task_holdout in the frozen original220 parent split; excluded from training labels'}
    validate_plan(plan)
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output/'manifest.json'
    path.write_text(json.dumps(plan, indent=2)+'\n')
    batch = {'domain': 'original', 'source': str(args.source), 'source_commit': revision, 'manifest': ref(path)}
    root = args.source.parent
    sam = ref(root/'sam3_feature_cache_startup_20261020.py')
    # The first30 comprise ten states per category, never thirty trials.
    for name, indices in [('startup', [0]), ('first30', list(range(30))), ('remaining60', list(range(30, len(selected))))]:
        output = {'selected_n': 8, 'training': False, 'confirmation': False, 'sam3_entry': sam,
            'batches': [{**batch, 'indices': indices[start:start+8]} for start in range(0, len(indices), 8)]}
        (args.output/(name+'_plan.json')).write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'states': len(selected), 'coverage': coverage, 'manifest': ref(path)}))


if __name__ == '__main__':
    main()
