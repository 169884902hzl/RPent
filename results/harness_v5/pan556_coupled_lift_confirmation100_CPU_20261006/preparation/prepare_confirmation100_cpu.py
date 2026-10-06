"""Register 99 known-unvisited original states plus one fixed reset repetition."""

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


LOCAL = Path(__file__).resolve().parents[4]
REMOTE = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent
REL = OUT.relative_to(LOCAL)
AUDIT = LOCAL / 'results/harness_v5/grasp_runtime546_monitor_CPU_20261006/coord_explicit_access_audit_CPU_20261006'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptor(path):
    return {'path': str(REMOTE / path.relative_to(LOCAL)), 'sha256': digest(path)}


audit_file, exclusions_file = AUDIT / 'report.json', AUDIT / 'explicit_original_state_exclusions.json'
audit = json.loads(audit_file.read_text())
exclusions = json.loads(exclusions_file.read_text())
assert digest(audit_file) == '9aee8deb0c0b86b202f564cd7889b15c9c61c518105ea65f945a1b17c5055953'
assert not audit['explicit_inputs_missing'] and not audit['input_sha_mismatches'] and not audit['identity_gaps']
excluded_sha = {r['state_sha256'] for r in exclusions['states']}
excluded_tuples = {(e['suite'],e['task'],e['seed']) for r in exclusions['states'] for e in r['original_scene_tuples']}
eligible = sorted(audit['eligible_cases'], key=lambda r:(r['episode']['task'],r['episode']['seed']))
assert len(eligible) == len({r['state_sha256'] for r in eligible}) == 99
for candidate in eligible:
    e = candidate['episode']
    assert candidate['state_sha256'] not in excluded_sha
    assert (e['suite'],e['task'],e['seed']) not in excluded_tuples

reference = OUT / 'source556_development_reference.json'
assert digest(reference) == '681a16637b5befc98ba7c3a4d4929ecae221fe522fc9f9ec8216a228f0e40ec8'
development = json.loads(reference.read_text())
condition = 'pan_coupled_lift_confirmation'
recipe = copy.deepcopy(next(iter(development['conditions'].values())))
assert recipe['pan_coupled_lift_v1'] is True
assert recipe['pan_cross_view_handle_v1'] is True
cases = []
for index, (candidate, reset) in enumerate([(r,0) for r in eligible] + [(eligible[0],1)]):
    e = candidate['episode']
    name = f"frypan_{e['suite']}_t{e['task']}_s{e['seed']}_r{reset}_{condition}"
    cases.append({**copy.deepcopy(candidate), 'name':name, 'condition':condition,
        'instruction':candidate['original_instruction'], 'group':'frypan','category':'frypan',
        'source':'official_original_LIBERO90', 'original_goal_source':True,
        'private_original_goal_predicates':copy.deepcopy(candidate['original_goal_predicates']),
        'official_init_index':e['seed'], 'state_hash_encoding':'C contiguous little endian float64',
        'trial_index':index, 'initial_state_repetition':reset,
        'registered_reset_id':f"{e['suite']}/t{e['task']}/s{e['seed']}/reset{reset}",
        'requires_current_visible_unique_binding':True,
        'is_correlated_registered_repeat':bool(reset), 'excluded_from_training':True})
assert len(cases) == len({r['name'] for r in cases}) == len({r['registered_reset_id'] for r in cases}) == 100
inputs = [descriptor(AUDIT / n) for n in ('report.json','explicit_access_input_index.json','explicit_original_state_exclusions.json')]
plan = {k:copy.deepcopy(development[k]) for k in ('base_config','choice_package','choice_package_files',
    'frypan_full_prompt','private_truth','truth_protocol','original90_grasp_diagnostic_v1',
    'infrastructure_retry_policy','private_goal_input_policy','robot_calibration_file','source_snapshot')}
plan.update({'purpose':'Independent original-pan confirmation: 100 registered first trials on99 known-unvisited states, plus one fixed repeated reset. No success-dependent redraw.',
    'cohort':'original_pan_coupled_lift_confirmation100_registered_resets',
    'groups':['frypan'],
    'conditions':{condition:recipe},'cases':cases,'first_attempts_per_condition_group':100,
    'producer':descriptor(Path(__file__)), 'source_recipe_reference':descriptor(reference),
    'selection':False, 'new_training_rows':0, 'qualification_authorized':False,
    'runtime_default_changed':False, 'no_physics_executed':True, 'run_status':'prepared_not_submitted',
    'measurement_target':'0.5s sustained physical grasp and public grasp-verifier agreement; original-task done remains separate',
    'budget':'Same SOURCE556 recipe:320 contact chunks of5 controls,10000 environment steps',
    'truth_inputs_do_not_control_actions':True,
    'original_goal_source_policy':'Original instruction and BDDL provenance retained. Pan skill can be an off-goal diagnostic; success does not certify the original full task.',
    'state_boundary':{'registered_first_attempts':100,'distinct_scene_tuples':99,'distinct_raw_states':99,
        'repeated_state':cases[-1]['episode'],'repeat_reset_ids':[cases[0]['registered_reset_id'],cases[-1]['registered_reset_id']],
        'unique100_requirement_added':False,'all_registered_states_excluded_from_training':True},
    'confirmation_audit':{'known_explicit_access_audit':inputs[0],'known_input_count':audit['explicit_input_count'],
        'registered_or_recorded_state_exclusions':inputs[2], 'known_state_exclusion_count':len(excluded_sha),
        'raw_state_overlap_count':0,'scene_tuple_overlap_count':0,'selection_and_old_confirmation_overlap_count':0,
        'audit_basis':'All228 exact currently indexed original manifests/ledgers, including4148/4149/4200/4227, prior registrations and conservative unexecuted reservations',
        'all_history_complete_claimed':False,'remaining_prepared_alias':audit['known_unresolved_reservation_aliases'],
        'sealed_metadata_scope_audit':audit['sealed_metadata_scope_audit']},
    'access_reservations':{'inputs':inputs,'prior_manifests':[]},
    'explicit_state_exclusions':inputs,
    'repetition_policy':'99 distinct states each reset0 once; lexicographically first task/seed repeats at reset1 as trial99. Different registered reset IDs are separate first attempts and form one dependent state cluster.',
    'wilson_policy':'Report known-label trial Wilson descriptively, plus distinct states/reset IDs and state-cluster summaries; repeated reset does not create a new independent state.',
    'first_physical_policy':'Never replace a first physical result with a later result; retain failures, zero-physics and unknown. Only one prephysics infrastructure retry per registered case.',
    'whole_manifest_infrastructure_limit':0.02})
manifest = OUT / 'pan_coupled_lift_confirmation100.json'
manifest.write_text(json.dumps(plan,indent=2)+'\n')
reservation = {'purpose':'Exclude every pan confirmation state from all later training and method-selection use',
    'manifest':descriptor(manifest),'distinct_states':99,'registered_first_attempts':100,
    'states':[{'episode':r['episode'],'state_sha256':r['state_sha256'],'exclude_from_training':True,
        'registered_reset_ids':[c['registered_reset_id'] for c in cases if c['state_sha256']==r['state_sha256']]}
        for r in eligible],'no_training_rows_generated':True}
(OUT / 'train_exclusion_reservations.json').write_text(json.dumps(reservation,indent=2)+'\n')
shards = [{'shard':i,'registered_trials':len(cases[i::8]),
    'trial_indices':[c['trial_index'] for c in cases[i::8]],
    'case_ids':[c['name'] for c in cases[i::8]]} for i in range(8)]
(OUT / 'shard_plan.json').write_text(json.dumps({'manifest':descriptor(manifest),'shards':shards,
    'array':'0-7%8','gpus_per_shard':1,'node_binding':None,'dependency':None,
    'all_cases_registered_before_outcomes':True},indent=2)+'\n')
print(json.dumps({'manifest':descriptor(manifest),'registered_first_attempts':100,'distinct_states':99,
    'per_task_trials':dict(Counter(r['episode']['task'] for r in cases)),
    'shard_trials':[s['registered_trials'] for s in shards],'new_physics':0}))
