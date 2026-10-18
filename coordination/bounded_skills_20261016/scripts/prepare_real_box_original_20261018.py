"""Add a real box cohort without changing the registered can or plate cases."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=20)
    args = parser.parse_args()
    if args.count < 1:
        parser.error('count must be positive')
    from rlinf.envs.libero.utils import benchmark
    import numpy as np
    import torch

    from scripts.bounded_state_exclusions import check_exclusions
    from scripts.v5_probe_preflight import load_pinned_manifest, validate_registered_states

    manifest, source, _ = load_pinned_manifest(args.source_manifest)
    suite_name, task_id = 'libero_object', 1
    suite = benchmark.get_benchmark(suite_name)()
    task = suite.get_task(task_id)
    assert task.language == 'pick up the cream cheese and place it in the basket'
    registered_bddl = next(c['bddl']['path'] for c in source['cases']
                           if c['episode']['suite'] == suite_name)
    original_root = Path(registered_bddl).resolve(strict=True).parents[2]
    bddl = (original_root / 'bddl_files' / task.problem_folder / task.bddl_file).resolve(strict=True)
    init_file = (original_root / 'init_files' / task.problem_folder / task.init_states_file).resolve(strict=True)
    states = torch.load(init_file, weights_only=False)
    runtime_states = suite.get_task_init_states(task_id)
    assert np.array_equal(np.asarray(states), np.asarray(runtime_states)), 'runtime original init bytes differ'
    cases, excluded = [], []
    for seed, state in enumerate(states):
        case = {
            'name': f'box_grab_place_{suite_name}_t{task_id}_s{seed}',
            'category': 'box_grab_place',
            'episode': {'suite': suite_name, 'task': task_id, 'seed': seed},
            'state_sha256': hashlib.sha256(np.asarray(state, dtype='<f8').tobytes()).hexdigest(),
            'bddl': {'path': str(bddl), 'sha256': hashlib.sha256(bddl.read_bytes()).hexdigest()},
            'init_file': {'path': str(init_file), 'sha256': hashlib.sha256(init_file.read_bytes()).hexdigest()},
            'purpose': 'development_feasibility_no_training',
        }
        try:
            check_exclusions([case], source['permanent_exclusions'])
        except ValueError as exc:
            if not str(exc).startswith('permanently excluded confirmation state:'):
                raise
            excluded.append({'episode': case['episode'], 'state_sha256': case['state_sha256']})
            continue
        cases.append(case)
        if len(cases) == args.count:
            break
    assert len(cases) == args.count, f'only {len(cases)} eligible original states'
    assert not ({c['state_sha256'] for c in source['cases']} & {c['state_sha256'] for c in cases})
    validate_registered_states(cases)
    exclusion_check = check_exclusions(cases, source['permanent_exclusions'])
    # Audit language in the already registered original-only catalog. Plate
    # destinations and the original push task are not plate grab/place tasks.
    plate_sources = [row for row in source['catalog'] if re.match(
        r'^(?:pick up|put|place) (?:the )?(?:(?:white|black|red) )?plate\b',
        row['instruction'].lower())]
    plan = copy.deepcopy(source)
    plan.update(
        version='bounded-original-real-box-supplement/1', cases=cases,
        missing_categories=[], arms=['oracle_k4'],
        original_cohort={'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
        producer={'path': str(Path(__file__).resolve()),
                  'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        coverage_audit={
            'registered_can_category': 'box_transfer',
            'registered_can_task': {'suite': 'libero_object', 'task': 0},
            'supplement_instruction': task.language,
            'plate_grab_place_tasks_in_registered_original_catalog': plate_sources,
            'plate_push_is_not_plate_grab_place': True,
            'original_cases_unchanged': True,
            'runtime_states_equal_registered_original_file': True,
            'selection_uses_policy_results': False,
            'skipped_permanent_confirmation_states': excluded,
            'permanent_exclusion_check': exclusion_check,
        }, training=False, confirmation=False,
    )
    plan.pop('preflight', None)
    output = args.output.expanduser().absolute()
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    _, checked, _ = load_pinned_manifest(output)
    print(json.dumps({'manifest': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                      'cases': len(cases), 'coverage_audit': plan['coverage_audit'],
                      'preflight': checked['preflight']}))


if __name__ == '__main__':
    main()
