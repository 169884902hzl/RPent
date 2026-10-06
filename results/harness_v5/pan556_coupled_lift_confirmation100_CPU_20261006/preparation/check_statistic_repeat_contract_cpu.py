"""CPU contract check only; synthetic repeat fixtures are never evaluation data."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
module_path = ROOT / 'scripts/summarize_v5_grasp543_20261006.py'
spec = importlib.util.spec_from_file_location('statistic',module_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
base = ROOT / 'results/harness_v5/grasp_runtime546_monitor_CPU_20261006'
preserved = []
for relative, role in [('receipt_runtime_error_fixed_1401UTC/pan_confirmation','confirmation'),
                       ('pan4227_coupled_lift_development_selection/final_completed_20261006','selection')]:
    folder = base / relative
    old = json.loads((folder/'report.json').read_text())
    rows = [json.loads(l) for l in (folder/'first_physical_cases.jsonl').read_text().splitlines()]
    assert len(old['by_manifest_condition_group']) == 1
    old_metric = next(iter(old['by_manifest_condition_group'].values()))
    cases = [{'name':r['case'],'condition':r['condition'],'group':r['group'],
        'episode':r['episode'],'state_sha256':r['state_sha256'],'analysis_role':role} for r in rows]
    current = m.metrics(cases,rows)
    for key,value in current.items():
        if key in old_metric:
            assert value == old_metric[key], (relative,key)
    preserved.append({'report':str(folder/'report.json'),
        'sha256':hashlib.sha256((folder/'report.json').read_bytes()).hexdigest(),
        'all_existing_metric_fields_equal':True})


def fixture(state_count):
    cases,rows = [],[]
    for i in range(100):
        sha = f'{i%state_count:064x}'
        case = {'name':f'synthetic_contract_{i}','condition':'synthetic_contract',
                'group':'frypan','state_sha256':sha,'analysis_role':'confirmation'}
        cases.append(case)
        rows.append({'case':case['name'],'state_sha256':sha,'sustained_posttrial_grasp':True,
            'public_grasp_verdict':True,'primary_outcome_success':True,
            'official_on_subtask_success':None,'official_original_task_done':None,
            'public_receipt_source':'first_receipt','final_receipt_present':True})
    return cases,rows


checks = []
for states in (50,99):
    cases,rows = fixture(states)
    result = m.metrics(cases,rows)
    assert result['single_class_threshold_evidence'] == 'supported_by_worst_case_bounds'
    assert result['distinct_registered_confirmation_states'] is False
    assert result['planned_unique_state_sha256'] == states
    assert result['state_cluster_summary']['planned_state_clusters'] == states
    checks.append({'synthetic_distinct_states':states,'registered_first_trials':100,
        'trial_count_not_unique_count_controls_numeric_evidence':True})
cases,rows = fixture(50)
rows[0].update(sustained_posttrial_grasp=None,public_grasp_verdict=None,primary_outcome_success=None)
unknown = m.metrics(cases,rows)
assert unknown['physical_success']['known'] == 99
assert unknown['physical_success']['unknown_or_not_yet_physical'] == 1
assert unknown['state_cluster_summary']['all_registered_grasp_trials_success']['known'] == 49
assert unknown['state_cluster_summary']['all_registered_grasp_trials_success']['unknown_or_not_yet_physical'] == 1
assert m.metrics(cases,rows[:99])['single_class_threshold_evidence'] is None
for case in cases:
    case['analysis_role']='selection'
assert m.metrics(cases,rows)['single_class_threshold_evidence'] is None
assert m.cohort_role('independent_confirmation_correlated_resets') == 'confirmation'
assert m.cohort_role('moka_selection_correlated_resets') == 'selection'
checks.append({'unknown_trials_and_unknown_clusters_preserved':True,
    '99_first_trials_do_not_meet100':True,'selection100_never_becomes_confirmation':True})
report={'scope':'CPU statistic contract fixtures only; no physical outcome, no confirmation metric',
    'statistic_sha256':hashlib.sha256(module_path.read_bytes()).hexdigest(),
    'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'synthetic_contract_checks':checks,'historical_metrics_preserved':preserved,
    'qualification_authorized':False,'new_physics':0,'new_training_rows':0}
(OUT/'statistic_repeat_contract_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'checks':checks,'historical_reports_preserved':len(preserved)}))
