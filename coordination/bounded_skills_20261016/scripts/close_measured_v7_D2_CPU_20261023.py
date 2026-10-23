"""Close the registered four-variant D2 evaluation and retain historical arms."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(path):
    return {r['case']: r for r in map(json.loads, path.read_text().splitlines())}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    denominator = 1+z*z/n
    centre = (k/n+z*z/(2*n))/denominator
    half = z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/denominator
    return [max(0., centre-half), min(1., centre+half)]


def branch_details(comparison, *, all_details=None):
    """Retain local scores, private progress, actual invocations, and unknowns."""
    failures, invocations, unknown, unsupported = [], Counter(), [], []
    for row in comparison:
        path = Path(row['summary']['path'])
        assert reference(path) == row['summary']
        data = json.loads(path.read_bytes())
        if data.get('unsupported'):
            unsupported.append({'case': row['case'], 'rules': data['unsupported'],
                'summary': row['summary'], 'reason': 'private_progress_rule_not_covered',
                'training': False})
        for subtask in data.get('subtasks', []):
            trials = subtask['trials']
            progress = [t.get('private_progress_success', t['success']) for t in trials]
            methods = {t['method'] for t in trials}
            records = []
            for trial, advanced in zip(trials, progress):
                requested = trial.get('vla_variant', {}).get('name')
                actual = trial.get('executed_vla_variants', [])
                if trial['method'] == 'call_vla':
                    invocations[(requested, 'trials')] += 1
                    invocations[(requested, 'trials_reaching_policy' if trial.get('vla_inference_calls', 0) else 'trials_without_policy_inference')] += 1
                    for call in actual:
                        parameters = call['parameters']
                        label = json.dumps({k: parameters.get(k) for k in ('preparation', 'mode', 'prompt_style')}, sort_keys=True)
                        invocations[(requested, 'actual_selected_parameters:'+label)] += 1
                records.append({'method': trial['method'], 'variant': trial.get('vla_variant'),
                    'seed': trial['trial_seed'], 'local_success': trial['success'],
                    'source_public_id': trial.get('source_public_id'),
                    'target_public_id': trial.get('target_public_id'),
                    'private_progress_success': advanced, 'native_task_success': trial.get('native_task_success'),
                    'registered_goal_satisfied_at_endpoint': trial.get('private_goal_satisfied_at_endpoint'),
                    'reason': trial['reason'], 'sim_steps': trial['sim_steps'],
                    'vla_inference_calls': trial.get('vla_inference_calls', 0),
                    'actual_selected_vla_variants': actual, 'choices': trial['choices']})
            detail = {'case': row['case'], 'suite': row['suite'],
                'subtask': subtask['subtask'], 'summary': row['summary'],
                'selection': subtask['selection'], 'trials': records,
                'training': False, 'evaluation_only': True,
                'scope': 'local subtask and private registered progress are separate; this is evaluation only'}
            if all_details is not None:
                all_details.append(detail)
            if any(value is None for value in progress):
                unknown.append(detail)
            elif progress and methods == {'self', 'call_vla'} and not any(progress):
                failures.append(detail)
    return failures, unknown, [{'requested_variant': k[0], 'measure': k[1], 'n': n}
        for k, n in sorted(invocations.items(), key=lambda item: str(item[0]))], unsupported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    output = args.run/'CPU_closed40'
    a1 = BASE.parent/'D2_preparation_c6b62442/preparation/A1_M_40_reference.json'
    aggregator = BASE/'aggregate_B2_D2_CPU_20261021.py'
    subprocess.run([sys.executable, str(aggregator), '--root', str(args.run),
        '--a1', str(a1), '--budgets', '1', '--shards', '0', '1', '2', '3',
        '--output', str(output)], check=True)
    manifest = json.loads((output/'manifest.json').read_bytes())
    current = rows(output/'paired_cases.jsonl')
    previous_path = BASE/'oracle_retry_fb9b3865/CPU_closed40/paired_cases.jsonl'
    model_path = BASE/'CPU_model40_closed_r1/paired_cases.jsonl'
    previous, model = rows(previous_path), rows(model_path)
    assert set(current) == set(previous) == set(model) and len(current) == 40
    assert not manifest['recovery']['1']['zero_replay_step_cases']
    comparison, stages, unknown = [], Counter(), Counter()
    table = ['| 局 | 新独立回放 | 新采样包络 | 前版回放 | 前版包络 | 模型 | A1-M |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name, row in sorted(current.items()):
        old = previous[name]
        a, b = row['first_replay_initial_physics_sha256'], old['first_replay_initial_physics_sha256']
        row.update(previous_replay_success=old['success'],
            previous_sampled_success=old['sampled_envelope_success'],
            model_success=model[name]['model_success'],
            same_complete_initial_as_previous=(a == b) if a and b else None)
        comparison.append(row)
        values = [row[k] for k in ('success', 'sampled_envelope_success',
            'previous_replay_success', 'previous_sampled_success', 'model_success', 'A1_M_success')]
        table.append('| '+name+' | '+' | '.join('?' if v is None else str(int(v)) for v in values)+' |')
        for subtask in row['subtask_selections']:
            for trial in subtask['trials']:
                if trial['success'] is False:
                    stages[trial['reason']] += 1
                elif trial['success'] is None:
                    unknown[trial['reason']] += 1
    data = output/'comparison.jsonl'
    data.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in comparison))
    table += ['', '同任务/初态编号协议；完整 A1 初态缺失。各历史臂的完整初态逐局认证状态见 comparison.jsonl，未相同的局不作因果选择错误归因。',
        '新臂同时增加公开锚点调用、额外采样和私有登记目标续接修复；差额不能全部归于新增方法。',
        '采样包络是从实测分支选择后的诊断，不是可部署策略的整局期望成功率。PRO/D2 只评测，不训练或调阈值。']
    (output/'comparison.md').write_text('\n'.join(table)+'\n')
    details = []
    failures, unknown_subtasks, invocation_counts, unsupported = branch_details(comparison, all_details=details)
    for name, values in (('both_failed_subtasks.jsonl', failures), ('unknown_subtasks.jsonl', unknown_subtasks),
            ('unsupported_cases.jsonl', unsupported), ('subtasks.jsonl', details)):
        (output/name).write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in values))
    method_groups = defaultdict(list)
    for detail in details:
        for trial in detail['trials']:
            variant = (trial.get('variant') or {}).get('name')
            method_groups[(detail['suite'], detail['subtask']['mode'], trial['method'], variant)].append(trial)
    method_report = []
    for key, group in sorted(method_groups.items(), key=lambda item: str(item[0])):
        known = [r for r in group if type(r['private_progress_success']) is bool]
        native = [r for r in group if type(r['native_task_success']) is bool]
        k = sum(r['private_progress_success'] for r in known)
        method_report.append({'suite': key[0], 'subtask_mode': key[1], 'method': key[2], 'variant': key[3],
            'trials': len(group), 'known': len(known), 'unknown': len(group)-len(known),
            'progress_success': k, 'progress_wilson95_over_repeated_trials': wilson(k, len(known)),
            'local_success': sum(r['local_success'] is True for r in group),
            'native_success': sum(r['native_task_success'] for r in native), 'native_known': len(native)})
    by_suite = {}
    for suite in sorted({r['suite'] for r in comparison}):
        group = [r for r in comparison if r['suite'] == suite]
        known = [r for r in group if type(r['sampled_envelope_success']) is bool]
        k = sum(r['sampled_envelope_success'] for r in known)
        by_suite[suite] = {'replay': manifest['recovery']['1']['by_suite'][suite],
            'sampled_success': k, 'sampled_known': len(known), 'sampled_unknown': len(group)-len(known),
            'sampled_wilson95': wilson(k, len(known))}
    report = {'manifest': reference(output/'manifest.json'), 'comparison': reference(data),
        'source_registration': reference(args.run/'preparation/D2_recovery1.json'),
        'previous': reference(previous_path), 'model': reference(model_path),
        'recovery1': manifest['recovery']['1'], 'by_suite': by_suite,
        'complete_initial_matches_with_previous': sum(r['same_complete_initial_as_previous'] is True for r in comparison),
        'complete_initial_unknown_with_previous': sum(r['same_complete_initial_as_previous'] is None for r in comparison),
        'improvements_vs_previous': [r['case'] for r in comparison if r['success'] and not r['previous_replay_success']],
        'regressions_vs_previous': [r['case'] for r in comparison if not r['success'] and r['previous_replay_success']],
        'raw_failed_branch_reasons': dict(stages),
        'raw_unknown_branch_reasons': dict(unknown),
        'both_failed_subtasks': reference(output/'both_failed_subtasks.jsonl'),
        'both_failed_subtask_count': len(failures),
        'unknown_subtasks': reference(output/'unknown_subtasks.jsonl'),
        'unknown_subtask_count': len(unknown_subtasks),
        'unsupported_private_rule_cases': reference(output/'unsupported_cases.jsonl'),
        'unsupported_private_rule_case_count': len(unsupported),
        'requested_vs_actual_vla': invocation_counts,
        'subtasks': reference(output/'subtasks.jsonl'),
        'method_by_suite_and_subtask': method_report,
        'subtask_rate_scope': 'private registered goal or local subtask progress; repeated trials conditional on previous sampled path; not native episode success or independent layouts',
        'failure_reason_scope': 'recorded stops; collision rejection is not proven false positive, handoff loss is not proof of physical dropping',
        'training': False, 'evaluation_only': True}
    (output/'delivery_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
