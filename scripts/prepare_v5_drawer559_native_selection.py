"""Prepare fixed SOURCE558 native drawer selection, never confirmation."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


PARENT_SHA = '59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387'
NATIVE_SHA = '2b29f8b2415ab01c29b344debd646e1f742f718584fed7a8dc2662724502faaa'
SOURCE = Path('/public/home/sunyihan/rpent_libero_eval/source_v5_drawer558_20261006')
SOURCE_COMMIT = '329e81961b100555078c33de8b872108d7b24b8a'
ARCHIVE_SHA = '080d3ce9841e766a40530e87dae74d60aa2396fe42f1af35af5d87511ebd2e8c'
METHOD = 'native_original160'


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def verify(reference):
    path = Path(reference['path'])
    if not path.is_absolute() or ref(path)['sha256'] != reference['sha256']:
        raise ValueError(f'Changed registered reference: {path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--native-template', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not all(p.is_absolute() for p in (args.parent, args.native_template, args.output)):
        parser.error('All paths must be absolute')
    parent_ref, native_ref = ref(args.parent), ref(args.native_template)
    if parent_ref['sha256'] != PARENT_SHA or native_ref['sha256'] != NATIVE_SHA:
        raise ValueError('Only the registered original parent and native SOURCE558 recipe are authorized')
    parent, native = json.loads(args.parent.read_text()), json.loads(args.native_template.read_text())
    if any(p.get('cohort') != 'selection' or p.get('qualification_authorized') is not False
           or p.get('new_training_rows') != 0 for p in (parent, native)):
        raise ValueError('Both inputs must remain development selection only')
    if len(parent['cases']) != 1200:
        raise ValueError('Parent1200 changed')
    source = native['source_snapshot']
    if (Path(source['path']) != SOURCE or source['commit'] != SOURCE_COMMIT
            or source['archive']['sha256'] != ARCHIVE_SHA or len(source['files']) != 24):
        raise ValueError('Immutable SOURCE558 identity changed')
    for item in [*source['files'], source['archive']]:
        verify(item)
    if any(not Path(x['path']).resolve().is_relative_to(SOURCE.resolve()) for x in source['files']):
        raise ValueError('Source file outside registered snapshot')
    condition = native['conditions'][METHOD]
    if (condition['executor'] != 'current' or condition['max_chunks'] != 160
            or condition['contact_approach'] != 'none'
            or condition['contact_prompt_source'] != 'registered_original_subtask'
            or condition['overrides']['drawer_current_binding_v4'] is not True):
        raise ValueError('Exact native reset/original/current-binding recipe changed')
    selected = [c for c in parent['cases'] if c['condition'] == 'current160'
                and c['type'] in ('drawer_open', 'drawer_close')]
    if Counter(c['type'] for c in selected) != {'drawer_open': 100, 'drawer_close': 100}:
        raise ValueError('Expected100 current160 cases of each drawer type')
    cases = []
    for old in selected:
        if old['episode']['suite'] != 'libero_90' or old['kind'] != 'articulate':
            raise ValueError('Only registered original LIBERO90 articulation cases')
        case = copy.deepcopy(old)
        episode = old['episode']
        case.update(name=f"drawer559_{old['type']}_libero90_t{episode['task']}_s{episode['seed']}_r{old['initial_state_repetition']}_{METHOD}",
                    condition=METHOD, subtask_prompt=old['original_instruction'],
                    prompt_origin='literal_registered_original_LIBERO90_instruction',
                    parent_case_name=old['name'],
                    reservation_scope='intentional reuse of original parent selection states; never confirmation')
        for key in ('episode', 'setup', 'state_sha256', 'official_init_index', 'type', 'mode',
                    'object_symbol', 'object_category', 'bddl', 'init_file', 'initial_state_repetition'):
            if case[key] != old[key]:
                raise ValueError(f'Parent case identity changed: {key}')
        cases.append(case)
    if len({c['name'] for c in cases}) != 200 or len({c['state_sha256'] for c in cases}) != 200:
        raise ValueError('Expected200 distinct original cases and states')
    plan = copy.deepcopy(native)
    for key in ('previous_selection_manifest', 'input_manifest', 'software_checks'):
        plan.pop(key, None)
    launcher = Path(__file__).with_name('run_v5_drawer559_native_selection.sbatch')
    plan.update(version='drawer559-native-original-selection/1',
                purpose='Original drawer native-method development selection; no confirmation admission',
                cohort='selection', selection='Reuse all100 open and100 close current160 parent cases without outcome filtering',
                confirmation='none; these registered parent selection states never qualify a method',
                cases=cases, cases_count=200, conditions={METHOD: copy.deepcopy(condition)},
                parent_manifest=parent_ref, native_recipe_reference=native_ref,
                producer=ref(__file__), producer_dependencies=[parent_ref, native_ref, ref(launcher)],
                source_snapshot=copy.deepcopy(source),
                pairing='One native trial per registered original parent current160 drawer case; prior arms and all prior failures preserved',
                state_repetition='200 distinct original parent selection states; intentional previous-selection reuse, not confirmation',
                preregistered_requests_by_type_arm={f'{typ}/{METHOD}': 100 for typ in ('drawer_open', 'drawer_close')},
                skill_chunk_contract={'controls_per_requested_chunk': 5, 'native_success_stops_chunk': False,
                                      'stop_at_external_budget': True, 'private_joint_or_predicate_used_for_control': False},
                diagnostic_factors={METHOD: 'Native/reset pose + literal original public instruction + current bbox binding',
                                    'fixed': 'Exact SOURCE558 recipe;160chunks and complete5controls per requested chunk',
                                    'native': 'No scripted handle approach; public sensing and original setup retained'},
                private_labels='Independent before/first-after requested endpoint truth is read-only scoring; never action, timing or stop input',
                metrics={'endpoint': 'Requested drawer before/first-after endpoint; full multi-goal original task success is separate',
                         'already_endpoint': 'Already-satisfied preservation, regression and initially-unsatisfied attainment remain separate',
                         'public_null': 'Retain unmeasured verdicts and unknown truth; no replacement labels',
                         'actual_budget': '160requested chunks x complete5controls; native termination never truncates a block',
                         'uncertainty': 'Wilson is descriptive for this selection cohort; no qualification admission'},
                access_reservations={'inputs': [parent_ref, native_ref], 'prior_manifests': [],
                                     'selected_unique_state_sha': 200, 'intentional_already_visited_selection_reuse': True},
                new_training_rows=0, qualification_authorized=False, runtime_default_changed=False,
                new_physical_trials=0, run_status='prepared_not_submitted')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / 'drawer559_native_original200_selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    shards = [{'shard': i, 'cases': len(cases[i::8]),
               'by_type': dict(Counter(c['type'] for c in cases[i::8])),
               'case_ids': [c['name'] for c in cases[i::8]]} for i in range(8)]
    preparation = {'manifest': ref(manifest), 'source': source,
                   'producer': ref(__file__), 'launcher': ref(launcher),
                   'parent_manifest': parent_ref, 'native_recipe_reference': native_ref,
                   'registered_trials': 200, 'distinct_states': 200,
                   'by_type': dict(Counter(c['type'] for c in cases)),
                   'by_type_task': [{'type': typ, 'task': task, 'count': count}
                                    for (typ, task), count in sorted(Counter((c['type'], c['episode']['task']) for c in cases).items())],
                   'setup_preserved': True, 'literal_original_prompts_preserved': True,
                   'native_condition_exactly_equal_source558': plan['conditions'][METHOD] == native['conditions'][METHOD],
                   'source_files_checked': 24, 'source_archive_checked': True,
                   'shards': shards, 'new_GPU_jobs': 0, 'new_physical_trials': 0,
                   'new_training_rows': 0, 'qualification_authorized': False}
    (args.output / 'preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
    print(json.dumps({'manifest': ref(manifest), 'registered_trials': 200, 'source_files_checked': 24,
                      'source': str(SOURCE), 'launcher': ref(launcher)}))


if __name__ == '__main__':
    main()
