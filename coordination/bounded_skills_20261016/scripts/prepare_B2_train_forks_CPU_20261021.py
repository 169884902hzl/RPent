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
    selected, coverage, lines = [], {}, {}
    for category in order:
        available = []
        for parent_id, parent in sorted(groups[category], key=lambda row: (row[1]['episode_id'], row[1]['source_link']['line'])):
            # A source subset is chosen by state/phase identity only, before
            # any new policy outcomes. Do not condition on episode success.
            annotation = parent['private_prefix_annotation_state']
            saved = load_annotation_state(annotation['path'], annotation['sha256'])
            status, old = saved['private_status'], saved['adapter']
            goal_index = next((i for i, value in enumerate(status['satisfied']) if not value), None)
            if goal_index is None:
                continue
            specs, unsupported = split_subtasks(status['goals'], old.ex.instruction)
            specs = [spec for spec in specs if spec['goal_index'] == goal_index]
            if not specs:
                continue
            source = saved['binding'].get('_bindings', {}).get(status['goals'][goal_index][1])
            held = old.held is not None and old.held == source
            mode = next((spec['mode'] for spec in specs
                if spec['mode'] != 'pick'), None) if held else specs[0]['mode']
            if mode is None:
                continue
            link = parent['source_link']
            if link['path'] not in lines:
                assert ref(link['path'])['sha256'] == link['sha256']
                lines[link['path']] = Path(link['path']).read_text().splitlines()
            row = json.loads(lines[link['path']][link['line']-1])
            snapshot = row['private_pre_execution_snapshot']
            assert snapshot['sha256'] == parent['state_sha256']
            phase = 'held' if held else 'initial' if row['index'] == 0 else 'intermediate'
            available.append((parent_id, parent, row, goal_index, mode, phase))
        wanted = []
        used_snapshots = set()
        used_initial = set()
        # Prefer measured intermediate/held states in half of each category;
        # then fill with different initial-state identities where possible.
        for phase_pool, quota in [('middle', args.per_category//2), ('all', args.per_category)]:
            for value in available:
                _, parent, row, _, _, phase = value
                if phase_pool == 'middle' and phase == 'initial':
                    continue
                if parent['state_sha256'] in used_snapshots or parent['initial_state_sha256'] in used_initial:
                    continue
                wanted.append(value)
                used_snapshots.add(parent['state_sha256'])
                used_initial.add(parent['initial_state_sha256'])
                if len(wanted) >= quota:
                    break
        coverage[category] = {'selected': len(wanted), 'available_logged_states': len(available),
            'unique_initial_states': len(used_initial),
            'phases': {phase: sum(value[-1] == phase for value in wanted) for phase in ('initial', 'intermediate', 'held')}}
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
        'selection': 'train+ok only; deterministic state/phase order, no new outcomes; distinct initial identities within category',
        'coverage': coverage, 'missing_categories': ['stove_on', 'stove_off'],
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
