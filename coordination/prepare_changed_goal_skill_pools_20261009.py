"""Preregister, then materialize genuine original-scene goal perturbations."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random

CELLS = [('vla_subtask', name) for name in ('bowl', 'bottle', 'box', 'cup', 'frypan', 'moka pot')]
CELLS += [('place', 'on'), ('place', 'in')]


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    return ref(path)


def register(output, *, moka_distractor=False):
    pools = []
    cells = [('vla_subtask', 'moka pot')] if moka_distractor else CELLS
    namespaces = [('selection', 10300000), ('confirmation', 10400000)] if moka_distractor else [
        ('selection', 10100000), ('confirmation', 10200000)]
    for split, start in namespaces:
        records = []
        for cell, (skill, category) in enumerate(cells):
            for index in range(400):
                seed = start + cell * 1000 + index
                rng = random.Random(seed)
                rule = {'skill': skill, 'category': category, 'layout_seed': seed,
                        'layout': 'swap_two_free_objects' if index % 2 else 'translate_free_object',
                        'xy_translation_m': [rng.uniform(-.1, .1), rng.uniform(-.1, .1)],
                        'world_yaw_delta_deg': rng.uniform(-45, 45), 'settle_steps': 30,
                        'goal_rule': 'require_changed_original_scene_on_in_target',
                        'scene_selection': 'lexical eligible scene, index modulo count',
                        'init_selection': 'index modulo official count',
                        'target_selection': 'lexical alternative list, index modulo count'}
                if moka_distractor:
                    rule['source_rule'] = 'non_goal_moka_in_original_scene'
                    rule['goal_rule'] = 'new_on_goal_for_original_distractor_at_existing_original_target'
                rule_sha = hashlib.sha256(json.dumps(rule, sort_keys=True).encode()).hexdigest()
                records.append({'name': f'{split}_{skill}_{category.replace(" ", "_")}_{seed}',
                                'rule': rule, 'rule_sha256': rule_sha,
                                'permanent_training_exclusion': split == 'confirmation'})
        pools.append(save(output / f'{split}.json', {'records': records, 'split': split,
                     'training_allowed': False, 'PRO_files_read': False, 'policy_outcomes_read': False}))
    return save(output / 'manifest.json', {'pools': pools, 'source': ref(Path(__file__)),
        'target_rule': 'Only on/in target type + region suffix appearing in original 40/LIBERO-90 goal predicates; instantiate using existing objects/regions in the current original scene. Exclude table init rectangles and source itself. Require a changed target and unsatisfied new goal before execution.',
        'selection_range': [namespaces[0][1], namespaces[0][1] + (len(cells)-1)*1000 + 399],
        'confirmation_range': [namespaces[1][1], namespaces[1][1] + (len(cells)-1)*1000 + 399],
        'source_rule': 'non-goal moka becomes transfer source; original goal replaced' if moka_distractor else 'retain_original_goal_source',
        'excluded_ranges': [[680100, 689999], [9200000, 9200999], [9300000, 9899999]],
        'states_per_cell': 100, 'geometric_reserves_per_cell': 400,
        'invalid_layouts_retained': True, 'native_and_private_goal_must_match': True,
        'confirmation_permanently_excluded_from_training': True,
        'minimum_training_distance_to_confirmed_moka_xy_m': .05,
        'methods_selected': False, 'physical_skill_trials': 0, 'training_allowed': False})


def materialize(args):
    import numpy as np
    from libero.libero.envs import OffScreenRenderEnv
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from scripts.materialize_v5_perturb_skill_pools_20261009 import (
        digest_state, eligible, materialize as layout, original_catalog)
    from scripts.prepare_v5_perturb_skill_selection_20261009 import public_name
    from scripts.v5_perturb_goal_diagnostic import (
        alternative_goals, apply_diagnostic_goal, goal_target_signatures)
    from scripts.v5_perturb_public_reference import source_reference

    if os.environ.get('LIBERO_TYPE') != 'standard':
        raise ValueError('LIBERO_TYPE=standard required')
    registration = json.loads((args.pool.parent / 'manifest.json').read_text())
    pinned = next(item for item in registration['pools'] if item['path'] == str(args.pool.resolve()))
    if ref(args.pool) != pinned:
        raise ValueError('Preregistered changed-goal pool changed')
    pool = json.loads(args.pool.read_text())
    catalog, suites = original_catalog()
    problems = {r['bddl']['path']: robosuite_parse_problem(r['bddl']['path']) for r in catalog}
    signatures = goal_target_signatures(problems.values())
    scenes = []
    source_rule = pool['records'][0]['rule'].get('source_rule')
    candidates = ([r for r in catalog if r.get('coarse_category') == 'moka pot' and not r['goals']]
                  if source_rule == 'non_goal_moka_in_original_scene' else
                  eligible(catalog, args.skill, args.category))
    for scene in candidates:
        goal = (['on', scene['source'], '__no_previous_target__'] if source_rule else
                next((g for g in scene['goals'] if len(g) == 3 and
                      (args.skill != 'place' or g[0] == args.category)), None))
        if goal:
            alternatives = alternative_goals(problems[scene['bddl']['path']], goal, signatures)
            if alternatives:
                scenes.append((scene, alternatives))
    if not scenes:
        raise ValueError('No original scene supports an alternative goal for this category')
    exclusions = set()
    for path in args.exclude:
        exclusions.update(r.get('state_sha256') for r in json.loads(path.read_text())['rows'])
    wrappers, rows, used = {}, [], set()
    declared = [r for r in pool['records'] if r['rule']['skill'] == args.skill and
                r['rule']['category'] == args.category]
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        with (args.output / 'preparation_attempts.jsonl').open('x') as ledger:
            for index, item in enumerate(declared):
                scene, alternatives = scenes[index % len(scenes)]
                key = (scene['suite'], scene['task'])
                if key not in wrappers:
                    wrappers[key] = OffScreenRenderEnv(bddl_file_name=scene['bddl']['path'],
                                                       camera_heights=256, camera_widths=256)
                    wrappers[key].reset()
                wrapper = wrappers[key]
                wrapper.env.parsed_problem['goal_state'] = copy.deepcopy(scene['all_goals'])
                # set_init_state restores physics, but not the episode-end
                # latch left by a previous registered goal during settling.
                wrapper.reset()
                row = {'name': item['name'], 'permanent_training_exclusion': item['permanent_training_exclusion']}
                try:
                    row.update(layout(wrapper, suites[key[0]].get_task_init_states(key[1]),
                                      scene, item, index, args.output))
                    state_path = Path(row['registered_layout_state']['path'])
                    state = json.loads(state_path.read_text())
                    goal = alternatives[index % len(alternatives)]
                    reference = f'the {public_name(goal[1])}'
                    target_reference = f'the {public_name(goal[2])}'
                    reference_error = False
                    if args.compile_source_reference:
                        from robosuite.utils.camera_utils import get_camera_extrinsic_matrix
                        rotation = get_camera_extrinsic_matrix(wrapper.sim, 'agentview')[:3, :3]
                        axes = []
                        for column in (0, 1):
                            axis = rotation[:, column].copy(); axis[2] = 0
                            axis /= np.linalg.norm(axis)
                            axes.append(axis.tolist())
                        geometry = state['preparation_provenance']['settled_geometry']
                        names = {symbol: public_name(symbol) for symbol in scene['objects']}
                        reference = source_reference(goal[1], geometry, axes, names)
                        if goal[2] in names:
                            target_reference = source_reference(goal[2], geometry, axes, names)
                        reference_error = reference is None or target_reference is None
                        state['source_reference_compilation'] = {
                            'version': 'original_layout_plain_reference/2', 'reference': reference,
                            'target_reference': target_reference,
                            'view_axes': axes, 'geometry_use': 'task sentence construction only',
                            'minimum_axis_gap_m': .04, 'policy_outcomes_used': False}
                    instruction = f'put {reference} {goal[0]} {target_reference}'
                    state.update(name=item['name'], skill_goal=goal, changed_goal=True,
                                 registered_goal_alternatives=alternatives,
                                 diagnostic_instruction=instruction,
                                 original_all_goals=scene['all_goals'])
                    evidence = apply_diagnostic_goal(wrapper, state)
                    invalid = list(row.get('invalid_reasons', []))
                    if reference_error:
                        invalid.append('source_reference_not_geometrically_unique')
                    if evidence['initially_satisfied']:
                        invalid.append('changed_goal_already_satisfied')
                    if state['state_sha256'] in used or state['state_sha256'] in exclusions:
                        invalid.append('state_overlap')
                    state.update(native_goal_preflight=evidence,
                                 status='invalid_layout' if invalid else 'prepared', invalid_reasons=invalid)
                    # Preparation alone owns this newly generated reset record.
                    state_path.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n')
                    row = {k:v for k,v in state.items() if k != 'rawstate'}
                    row.update(registered_layout_state=ref(state_path))
                    used.add(state['state_sha256'])
                except Exception as error:
                    row.update(status='preparation_error', error=repr(error))
                rows.append(row)
                ledger.write(json.dumps(row, allow_nan=False) + '\n'); ledger.flush()
                print(json.dumps({'name': item['name'], 'status': row['status']}), flush=True)
                if sum(r['status'] == 'prepared' for r in rows) >= 100:
                    break
    finally:
        for wrapper in wrappers.values():
            wrapper.close()
    report = {'pool': ref(args.pool), 'generator': ref(Path(__file__)), 'signatures': signatures,
              'rows': rows, 'changed_goal_valid': sum(r['status'] == 'prepared' for r in rows),
              'policy_outcomes_read': False, 'PRO_files_read': False, 'training_allowed': False,
              'excluded_pools': [ref(p) for p in args.exclude], 'physical_skill_trials': 0}
    save(args.output / 'manifest.json', report)
    if report['changed_goal_valid'] < 100 or any(r['status'] == 'preparation_error' for r in rows):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--moka-distractor-register', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pool', type=Path)
    parser.add_argument('--skill')
    parser.add_argument('--category')
    parser.add_argument('--exclude', type=Path, action='append', default=[])
    parser.add_argument('--compile-source-reference', action='store_true')
    args = parser.parse_args()
    if args.register:
        print(json.dumps(register(args.output, moka_distractor=args.moka_distractor_register)))
    else:
        materialize(args)


if __name__ == '__main__':
    main()
