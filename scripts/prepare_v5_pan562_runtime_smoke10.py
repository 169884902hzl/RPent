"""Pin a same10 visited-state PAN runtime smoke, never confirmation."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_pan562_20261006'
COMMIT = 'e6f69a80ed2d26188a9b3233b72ad220d93cede8'
ARCHIVE = ROOT / 'source_v5_pan562_20261006.tar.gz'
ARCHIVE_SHA = 'bd65b1ed75867ce582fe49309d7cc46aed796a8221174d5bdb004bfcbd6e5cf7'
PARENT = ROOT / 'results/harness_v5/pan556_coupled_lift_development10_CPU_20261006/preparation/pan_coupled_lift_same10_selection.json'
PARENT_SHA = '681a16637b5befc98ba7c3a4d4929ecae221fe522fc9f9ec8216a228f0e40ec8'
CONFIRMATION = ROOT / 'results/harness_v5/pan556_coupled_lift_confirmation100_CPU_20261006/preparation/pan_coupled_lift_confirmation100.json'
CONFIRMATION_SHA = '32e11afe73db40727b6f9574e68be2127033c4fdd47f7ea355b3debe23987737'
METHOD = 'pan_runtime_direct_development'


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def function_body(path, name):
    tree = ast.parse(Path(path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error('Absolute output required')
    if ref(PARENT)['sha256'] != PARENT_SHA or ref(ARCHIVE)['sha256'] != ARCHIVE_SHA:
        raise ValueError('Original10 or immutable SOURCE562 archive changed')
    if ref(CONFIRMATION)['sha256'] != CONFIRMATION_SHA:
        raise ValueError('Confirmation reservation changed')
    old = json.loads(PARENT.read_text())
    confirmation = json.loads(CONFIRMATION.read_text())
    if len(old['cases']) != 10 or old['qualification_authorized'] is not False:
        raise ValueError('Only same10 development states authorized')
    functions = ('measured_pan_handle_views', 'rpent_pick_then_independent_handle_measure')
    old_probe = Path(old['source_snapshot']['path']) / 'scripts/probe_v5_grasp449_20261005.py'
    shared = SOURCE / 'robots/libero/v5_pan_grasp.py'
    ast_equality = {name: function_body(old_probe, name) == function_body(shared, name) for name in functions}
    if not all(ast_equality.values()):
        raise ValueError('Confirmed public function body changed')
    condition = copy.deepcopy(next(iter(old['conditions'].values())))
    condition['overrides'].update(grasp_category_profiles_v1=True, pan_coupled_lift_v1=True)
    cases = copy.deepcopy(old['cases'])
    for case in cases:
        case.update(parent_development_case_name=case['name'], condition=METHOD,
                    name=case['name'].replace('pan_coupled_lift_development', METHOD),
                    development_replay_of_job=4227)
    confirmation_states = {c['state_sha256'] for c in confirmation['cases']}
    if any(c['state_sha256'] in confirmation_states for c in cases):
        raise ValueError('Runtime smoke overlaps4246 confirmation states')
    drawer_manifest = ROOT / 'results/harness_v5/drawer558_binding_selection_CPU_20261006/preparation/drawer558_same5_binding_selection.json'
    relative_files = [x['relative_path'] for x in json.loads(drawer_manifest.read_text())['source_snapshot']['files']]
    relative_files.append('robots/libero/v5_pan_grasp.py')
    source = {'path': str(SOURCE), 'commit': COMMIT, 'archive': ref(ARCHIVE),
              'files': [{'relative_path': name, **ref(SOURCE / name)} for name in relative_files]}
    keys = ('base_config', 'choice_package', 'choice_package_files', 'frypan_full_prompt', 'private_truth',
            'truth_protocol', 'original90_grasp_diagnostic_v1', 'infrastructure_retry_policy',
            'private_goal_input_policy', 'robot_calibration_file')
    plan = {key: copy.deepcopy(old[key]) for key in keys if key in old}
    launcher = Path(__file__).with_name('run_v5_pan562_runtime_smoke10.sbatch')
    route_check = ROOT / 'results/harness_v5/pan562_runtime_smoke10_CPU_20261006/check_runtime_entry_cpu.py'
    plan.update(version='pan562-runtime-direct-same10-selection/1',
                purpose='Same10 visited original development states; exercise real runtime direct PAN profile',
                cohort='original_pan_runtime_profile_development_selection', selection=True,
                groups=copy.deepcopy(old['groups']), conditions={METHOD: condition}, cases=cases,
                first_attempts_per_condition_group=10, source_snapshot=source,
                parent_development_manifest=ref(PARENT), producer=ref(__file__),
                producer_dependencies=[ref(launcher), ref(route_check)],
                confirmation_reservation={'manifest': ref(CONFIRMATION), 'state_overlap_count': 0,
                                          'read_scope': 'Registered state SHA only; no confirmation outcomes or physical state replay'},
                runtime_entry={'required': 'V5Executor._execute -> execute_category_grasp(PAN) -> execute_pan_coupled_grasp',
                               'probe_vla_override_must_not_execute': True,
                               'contact_prompt': 'pick up the frying pan', 'contact_max_chunks': 320,
                               'trial_lift_m': .10, 'coupled_lift_m': .05,
                               'cross_view_handle_v1': True, 'coupled_lift_v1': True,
                               'public_calibration': 'Exact original10 condition grasp_measurement_calibration'},
                function_body_AST_unchanged_from_source556=ast_equality,
                source561_cpu_finding={'snapshot': str(ROOT / 'source_v5_pan561_20261006'),
                                       'finding': 'Runtime prompt differed from actual selected_only+frying pan alias contact phrase',
                                       'old_runtime_phrase': 'pick up the frypan and lift it clear of its starting surface',
                                       'restored_SOURCE562_phrase': 'pick up the frying pan', 'GPU_executions': 0,
                                       'source561_modified': False, 'source561_registered_for_execution': False},
                state_boundary={'same10_visited_development_states': True, 'distinct_states': 10,
                                'confirmation4246_states_used': 0, 'new_confirmation_requested': False},
                budget=copy.deepcopy(old['budget']), measurement_target=copy.deepcopy(old['measurement_target']),
                runtime_default_changed=False, new_training_rows=0, qualification_authorized=False,
                run_status='prepared_not_submitted', no_physics_executed=True,
                first_physical_policy='Retain all prior and current physical outcomes; smoke never replaces4227 or4246')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / 'pan562_runtime_direct_same10_selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    preparation = {'manifest': ref(manifest), 'source': source, 'producer': ref(__file__),
                   'launcher': ref(launcher), 'same_visited_cases': [c['episode'] for c in cases],
                   'confirmation_state_overlap': 0, 'runtime_entry': plan['runtime_entry'],
                   'function_body_AST_unchanged': ast_equality, 'new_physics': 0, 'new_GPU_jobs': 0,
                   'new_training_rows': 0, 'qualification_authorized': False}
    (args.output / 'preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
    print(json.dumps({'manifest': ref(manifest), 'launcher': ref(launcher), 'source_files': len(source['files'])}))


if __name__ == '__main__':
    main()
