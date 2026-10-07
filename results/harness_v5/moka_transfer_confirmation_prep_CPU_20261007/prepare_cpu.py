"""Pin original moka-transfer evidence, visited smoke and five-class statistics."""

import copy
import hashlib
import json
import math
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'preparation'


def identity(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read(relative, expected=None):
    ref = identity(ROOT / relative)
    if expected is not None and ref['sha256'] != expected:
        raise ValueError('Pinned evidence changed: ' + ref['path'])
    return json.loads(Path(ref['path']).read_text()), ref


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return identity(path)


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [max(0., centre-half), min(1., centre+half)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original, original_ref = read(
        'results/harness_v5/grasp_next_methods_20261006/preparation/moka_methods_selection.json',
        '5f9044d6236128de6900b7b8ed15c0e792db615e117a6affe6be6dfc96061daa')
    selection, selection_ref = read(
        'results/harness_v5/grasp_runtime546_monitor_CPU_20261006/final_completed_4149_CPU_20261006/moka_selection/report.json',
        '311a7da310ef4b8db2e42480e56dde767935f18104e7895b2c675c9661cca579')
    selected = next(v for k, v in selection['by_manifest_condition_group'].items()
                    if '/moka_original_complete_subtask/' in k)
    old, old_ref = read('results/harness_v5/moka_methods_readonly_CPU_20261006/report/report.json')
    old_summary = next(v for v in old['groups'] if v['cohort'] == 'confirmation_job3685')
    write('selection_evidence.json', {
        'selection_report': selection_ref, 'selection_manifest': original_ref,
        'complete_original_subtask': selected,
        'old_split_grasp_confirmation_report': old_ref,
        'old_split_grasp_confirmation': old_summary,
        'placement_public_verifier_agreement_measured_in_selection': False,
        'old_98_percent_scope': 'Public grasp verdict versus posttrial sustained grasp only',
        'new_physics': 0, 'new_training_rows': 0})
    four, four_ref = read(
        'results/harness_v5/grasp_runtime546_monitor_CPU_20261006/four_class_existing_confirmation/report.json',
        '06e94061fc6e59214ce1b8f66b98444b432278f505e236c0e9af709cf54d153d')
    pan, pan_ref = read(
        'results/harness_v5/pan559_monitor_CPU_20261006/final_20261006T160044.400615Z/statistic/report.json',
        '1421284ba135b8b5eb0d7297436c72ad9c3f2830edd0cdb80349fd8a3ac8c869')
    classes = copy.deepcopy(four['by_class'])
    pan_stats = next(iter(pan['by_manifest_condition_group'].values()))
    classes['frypan'] = {key: copy.deepcopy(pan_stats[key]) for key in (
        'first_physical_attempts', 'observed_unique_state_sha256', 'physical_success',
        'verifier_agreement', 'confusion', 'observed_correlated_repeat_requests')}
    aggregate = {}
    for key in ('physical_success', 'verifier_agreement'):
        k = sum(v[key]['successes'] for v in classes.values())
        known = sum(v[key]['known'] for v in classes.values())
        n = sum(v[key]['denominator'] for v in classes.values())
        aggregate[key] = {'successes': k, 'known': known, 'unknown': n-known,
                          'denominator': n, 'known_rate': k/known,
                          'worst_case_rate': k/n, 'best_case_rate': (k+n-known)/n,
                          'known_wilson_95CI_descriptive': wilson(k, known),
                          'all_planned_conservative_wilson_95CI_descriptive': wilson(k, n)}
    write('five_class_existing_confirmation.json', {
        'inputs': [four_ref, pan_ref], 'by_class': classes, 'aggregate': aggregate,
        'source_strata': {**four['by_class_source'], **pan['by_source_manifest_condition_group']},
        'unknown_policy': 'Preserve the box and mug unknowns; no replacement labels or retries',
        'interval_scope': 'Descriptive mixture of frozen sources; pan has 99 states and one registered repeat. Wilson does not establish independent trials or one current-runtime qualification.',
        'moka_transfer_excluded_from_grasp_aggregate': True,
        'new_physics': 0, 'new_training_rows': 0})
    profiles, profile_ref = read('results/harness_v5/grasp492_first4_confirmation_20261005/preparation/full.json')
    pan562, pan562_ref = read('results/harness_v5/pan562_runtime_smoke10_CPU_20261006/preparation/pan562_runtime_direct_same10_selection.json',
                             '6800976d91fab44c3195bed378e83370aa1ae0ffa6f27615a537e91af75b9e63')
    pan_recipe = copy.deepcopy(pan562['conditions']['pan_runtime_direct_development'])
    calibration_ref = write('pan562_grasp_measurement_calibration.json',
                            pan_recipe['overrides']['grasp_measurement_calibration'])
    write('five_class_profile_overrides.json', {
        'scope': 'Four formal frozen class recipes and the current pan562 direct runtime development recipe; not a new combined confirmation',
        'inputs': [profile_ref, pan562_ref], 'grasp_measurement_calibration': calibration_ref,
        'by_class': {**{name.removeprefix('confirm_'): value for name, value in profiles['conditions'].items()},
                     'frypan': pan_recipe}})
    parent, parent_ref = read('results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json')
    condition = copy.deepcopy(original['conditions']['moka_original_complete_subtask'])
    condition['overrides'].update(native_grasp_stop_v1=False, strict_place_v6=True,
        target_cache_v1=True, subtask_place_remeasure_v7=True,
        subtask_release_reverify_v8=True, subtask_place_observe_retreat_v9=True)
    cases, seen = [], set()
    for case in original['cases']:
        if case['condition'] != 'moka_original_complete_subtask' or case['state_sha256'] in seen:
            continue
        seen.add(case['state_sha256'])
        case = copy.deepcopy(case)
        case['name'] = f"moka_transfer_visited_{case['episode']['suite']}_t{case['episode']['task']}_s{case['episode']['seed']}"
        case['initial_state_repetition'] = 0
        case['condition'] = 'moka_original_complete_public_placement_smoke'
        case['previously_used_for_selection'] = True
        case['excluded_from_training'] = True
        for key, asset_kind in [('bddl', 'bddl_files'), ('init_file', 'init_files')]:
            asset = ROOT / '.venv/lib/python3.10/site-packages/libero/libero' / asset_kind / case['episode']['suite'] / Path(case[key]['path']).name
            standard_ref = identity(asset)
            if standard_ref['sha256'] != case[key]['sha256']:
                raise ValueError('Official standard asset differs from registered original bytes')
            case[key] = standard_ref
        cases.append(case)
        if len(cases) == 10:
            break
    plan = {key: copy.deepcopy(original[key]) for key in (
        'base_config', 'choice_package', 'choice_package_files', 'frypan_full_prompt',
        'budget', 'infrastructure_retry_policy', 'private_goal_input_policy') if key in original}
    plan.update(purpose='Ten visited original moka states: complete original sentence and strict public placement development smoke',
        source_snapshot=parent['source_snapshot'], source_identity_parent=parent_ref,
        producer=identity(__file__), producer_dependencies=[
            identity(ROOT / 'scripts/probe_v5_moka_transfer_public_20261007.py'),
            identity(ROOT / 'scripts/serve_v5_moka_transfer_registered_20261007.py'),
            identity(ROOT / 'scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch')],
        selection={'analysis_role': 'development_visited_state_smoke', 'confirmation': False,
                   'parent_selection': original_ref},
        conditions={'moka_original_complete_public_placement_smoke': condition}, cases=cases,
        private_truth=True, truth_protocol=None, private_goal_metrics=True,
        primary_outcome='Original selected moka On stove predicate after execution',
        public_agreement='Strict public placement verdict versus that private On predicate',
        original90_grasp_diagnostic_v1=True, new_training_rows=0,
        qualification_authorized=False, runtime_default_changed=False,
        new_physics_executed_in_preparation=0, first_physical_policy='Keep all first physical outcomes; never rerun physical failure')
    manifest_ref = write('moka_original_public_placement_visited10.json', plan)
    print(json.dumps({'smoke_manifest': manifest_ref, 'source': plan['source_snapshot']['path'],
                      'five_class_aggregate': aggregate, 'calibration': calibration_ref}))


if __name__ == '__main__':
    main()
