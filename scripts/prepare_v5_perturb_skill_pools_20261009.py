"""Preregister original-only perturbation rules before inspecting outcomes."""

import argparse
import hashlib
import json
from pathlib import Path
import random

ORIGINAL = ("libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90")
CELLS = (
    *(('grasp', name) for name in ('bowl', 'bottle', 'box', 'cup', 'frypan')),
    *(('vla_subtask', name) for name in ('bowl', 'bottle', 'box', 'cup', 'frypan', 'moka pot')),
    ('place', 'on'), ('place', 'in'),
    *(('articulate', name) for name in ('drawer_open', 'drawer_close', 'stove_turn_on',
                                     'stove_turn_off', 'microwave_open', 'microwave_close')),
)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pools = []
    # Independent seed namespaces, each far outside the existing train/confirm
    # ranges. All declared confirmation rules are excluded before execution.
    for split, first in (('selection', 9301000), ('confirmation', 9401000)):
        records = []
        for cell, (skill, category) in enumerate(CELLS):
            for attempt in range(100):
                seed = first + cell * 100 + attempt
                rng = random.Random(seed)
                rule = {
                    'skill': skill, 'category': category, 'layout_seed': seed,
                    'original_scene_selection': 'lexical eligible original scene list, attempt modulo list size',
                    'base_init_selection': 'attempt modulo official state count; raw-state hash pinned before materialization',
                    'layout': 'swap_two_free_objects' if attempt % 2 else 'translate_free_object',
                    'xy_translation_m': [rng.uniform(-.10, .10), rng.uniform(-.10, .10)],
                    'world_yaw_delta_deg': rng.uniform(-45., 45.),
                    'goal_rule': ('rotate_eligible_on_in_target' if skill in ('vla_subtask', 'place')
                                  and attempt % 3 == 0 else 'retain_original_goal'),
                    'fixture_background_perturbation': 'swap_or_translate_unattached_objects_only',
                    'settle_steps': 30,
                    'validity': 'private geometry/contact checks during preparation; no policy outcomes used',
                    'invalid_layout': 'retain invalid record; deterministic next declared attempt index, before skill execution',
                    'private_values': 'preparation and labels only; runtime reads measured RGB-D and proprioception',
                }
                records.append({'name': f'{split}_{skill}_{category.replace(" ", "_")}_{seed}',
                                'rule': rule, 'rule_sha256': sha(rule),
                                'permanent_training_exclusion': split == 'confirmation',
                                'state_sha256': None, 'status': 'preregistered_not_materialized'})
        path = args.output / f'{split}.json'
        payload = {'schema': 'original-perturbed-skill-pool/1', 'split': split,
                   'original_suites': ORIGINAL, 'cells': [{'skill': a, 'category': b, 'planned': 100} for a,b in CELLS],
                   'records': records, 'PRO_files_read': False, 'policy_outcomes_read': False,
                   'training_allowed': False, 'physical_skill_trials': 0,
                   'confirmation_gate': {'kind': 'internal', 'overall_success': .95,
                                         'minimum_category_success': .90, 'verifier_agreement': .95}}
        path.write_text(json.dumps(payload, indent=2) + '\n')
        pools.append({'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'planned': len(records), 'seed_min': min(r['rule']['layout_seed'] for r in records),
                      'seed_max': max(r['rule']['layout_seed'] for r in records)})
    manifest = {'generator': {'path': str(Path(__file__).resolve()),
                             'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                'pools': pools, 'planned_cells_per_split': len(CELLS),
                'excluded_existing_ranges': [[680100,689999], [9200000,9200999]],
                'confirmation_permanently_excluded_from_training': True,
                'minimum_training_distance_to_confirmed_moka_xy_m': .05,
                'materialization_pending': True, 'skill_execution_pending': True,
                'training_allowed': False, 'physics_executed': 0,
                'purpose': 'original-only perturbation selection/confirmation; not PRO or training inputs'}
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'planned_per_split': len(CELLS)*100, 'physics_executed': 0}))


if __name__ == '__main__':
    main()
