"""Register measured forks from actual original-train layout prefix captures."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref):
    if reference(ref['path']) != ref:
        raise ValueError('captured input changed: ' + ref['path'])
    return Path(ref['path'])


def measured_case(point, default, index):
    """Keep original split lineage distinct from the new physical snapshot."""
    report = json.loads(checked(point['construction_report']).read_bytes())
    parents = json.loads(checked(point['frozen_parent_index']).read_bytes())['parents']
    parent_id = report['parent_id']
    parent = report['layout']['parent']
    if (parents[parent_id]['split'] != 'train' or parent['split'] != 'train'
            or report['layout']['PRO'] or report['layout']['D2']
            or report['layout']['confirmation'] or point['confirmation']):
        raise ValueError('measured own-layout forks require original train lineage')
    if not point['label_eligible'] or point['subtask'] is None:
        raise ValueError('captured position has no existing oracle subtask rule')
    for key in ('physics', 'annotation', 'generated_state', 'checkpoint'):
        checked(point[key])
    case = copy.deepcopy(point['case'])
    if any(case['episode'][key] != parent[key] for key in ('suite', 'task', 'seed')):
        raise ValueError('captured layout and original task identity differ')
    if case['bddl'] != report['original_bddl']:
        raise ValueError('own layout changed original task wording')
    checked(case['bddl'])
    # The existing launcher validates this official parent hash. The actual
    # branch identity is separately bound to the new complete physics below.
    case.update(name=case['name'] + f'_prefix{point["index"]:03d}',
        state_sha256=parent['initial_state_sha256'],
        source_training_parent_ids=[parent_id],
        saved_start_phase=point['phase'], identity_domain='own_original_train_layout')
    own = {key: point[key] for key in
        ('generated_state', 'construction_report', 'frozen_parent_index')}
    own.update(layout_seed=point['layout_seed'], prefix_checkpoint=point['checkpoint'],
        capture_source_commit=point['source_commit'],
        identity_scope='new authored world and actual prefix; original parent is split lineage only')
    case['diagnostic'] = {'kind': 'original_fork', 'domain': 'original',
        'own_layout': own, 'subtask_mode': point['subtask']['mode'],
        'goal_index': point['subtask']['goal_index'],
        'original_subtask_start': {'physics': point['physics'],
            'annotation': point['annotation'], 'decision_index': point['prefix_decisions']},
        'trial_seed_base': 34000000 + index * 10000,
        'include_self': True, 'self_repeats': 2,
        'targeted_vla_measurement_v1': True,
        'vla_variants': [
            {'name': 'in_place', 'parameters': {'preparation': 'in_place'}},
            {'name': 'initial_pose', 'parameters': {'preparation': 'initial_pose'}},
            {'name': 'full_task', 'parameters': {'mode': 'task',
                'preparation': 'in_place', 'prompt_style': 'full_task'}},
        ], 'budget': copy.deepcopy(default['cases'][0]['diagnostic']['budget'])}
    return case


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'default-manifest', 'captures', 'sam-entry', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=20)
    a = p.parse_args()
    source = a.source.resolve(strict=True)
    revision = json.loads((source / 'SOURCE_REVISION.json').read_bytes())['commit']
    default = json.loads(a.default_manifest.read_bytes())
    selected, seen, records = [], set(), []
    for path in sorted(a.captures.glob('case*/episode/point*/point.json')):
        point = json.loads(path.read_bytes())
        if not point['label_eligible']:
            continue
        identity = point['physics']['sha256']
        if identity in seen:
            continue
        selected.append(measured_case(point, default, len(selected)))
        seen.add(identity)
        records.append(reference(path))
    if not selected:
        raise ValueError('no actual eligible prefix captures')
    plan = {key: copy.deepcopy(default[key]) for key in
        ('evaluation', 'permanent_exclusions', 'original_cohort')}
    plan.update(source_commit=revision, training=False, confirmation=False,
        schema6_source=True, vla_options_v2=True, cases=selected,
        frozen_parent_index=point['frozen_parent_index'],
        own_layout_captures=records,
        selection='all distinct eligible actual prefix captures in identity order; no method outcomes used')
    # This reuses the owning runtime's input validation; it executes no physics.
    import sys
    sys.path.insert(0, str(source))
    from scripts.probe_bounded_hybrid_repair import validate_plan
    from scripts.bounded_state_exclusions import check_exclusions
    validate_plan(plan)
    exclusions = check_exclusions(selected, plan['permanent_exclusions'])
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = a.output / 'manifest.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    batch = {'domain': 'original', 'source': str(source), 'source_commit': revision,
        'manifest': reference(manifest)}
    common = {'training': False, 'confirmation': False,
        'sam3_entry': reference(a.sam_entry), 'selected_n': 8}
    for name, groups in (
            ('startup_plan', [[0]]),
            ('batch_plan', [list(range(i, min(i + a.batch_size, len(selected))))
                for i in range(0, len(selected), a.batch_size)])):
        value = {**common, 'batches': [{**batch, 'indices': group} for group in groups]}
        (a.output / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    registration = {'manifest': reference(manifest), 'states': len(selected),
        'by_category': dict(Counter(c['category'] for c in selected)),
        'by_phase': dict(Counter(c['saved_start_phase'] for c in selected)),
        'physical_trials_per_state': {'self': 2, 'in_place': 3, 'initial_pose': 3, 'full_task': 3},
        'exclusions': exclusions, 'source_commit': revision,
        'training': False, 'physical_labels_collected': 0}
    (a.output / 'registration.json').write_text(json.dumps(registration, indent=2) + '\n')
    print(json.dumps(registration))


if __name__ == '__main__':
    main()
