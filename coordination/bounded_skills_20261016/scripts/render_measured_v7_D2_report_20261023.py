"""Render the closed evaluation artifacts; never execute or rescore a rollout."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    d = 1 + z*z/n
    c = (k/n + z*z/(2*n))/d
    h = z*math.sqrt(k*(n-k)/n**3 + z*z/(4*n*n))/d
    return [max(0., c-h), min(1., c+h)]


def interval(value):
    return '—' if value is None else f'{100*value[0]:.1f}–{100*value[1]:.1f}%'


def rate(values):
    known = [v for v in values if type(v) is bool]
    return f'{sum(known)}/{len(known)}' + (f' + {len(values)-len(known)} unknown' if len(known) != len(values) else '')


def measured_rate(values):
    known = [v for v in values if type(v) is bool]
    return {'success': sum(known), 'known': len(known), 'unknown': len(values)-len(known),
            'wilson95_over_repeated_trials': wilson(sum(known), len(known))}


def rate_ci(values):
    return rate(values)+' ('+interval(measured_rate(values)['wilson95_over_repeated_trials'])+')'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory
    data = json.loads((root/'measured_v7_D2_delivery_summary.json').read_text())
    rows = [json.loads(s) for s in (root/'measured_v7_D2_comparison.jsonl').read_text().splitlines()]
    details = [json.loads(s) for s in (root/'measured_v7_D2_subtasks.jsonl').read_text().splitlines()]
    failed = [json.loads(s) for s in (root/'measured_v7_D2_both_failed_subtasks.jsonl').read_text().splitlines()]
    unsupported = [json.loads(s) for s in (root/'measured_v7_D2_unsupported_cases.jsonl').read_text().splitlines()]
    stats = data['recovery1']
    assert stats['closed'] == len(rows) == 40 and not stats['missing'] and not stats['zero_replay_step_cases']
    replay_gaps = [r['case'] for r in rows if r['sampled_envelope_success'] is True and not r['success']]
    reverse_gaps = [r['case'] for r in rows if r['success'] and r['sampled_envelope_success'] is False]
    lines = [
        f"恢复预算 1 档的 40 局采样与独立整局回放全部闭合；原生整局成功 {stats['success']}/40，Wilson 95% {interval(stats['wilson95'])}。",
        f"实测采样包络 {stats['sampled_bound_success']}/{stats['sampled_bound_known']}，另 {40-stats['sampled_bound_known']} 局私有规则未覆盖；已知分母的 Wilson 95% {interval(stats['sampled_bound_wilson95'])}。",
        f"前版回放 23/40、模型 10/40、A1-M 28/40；新旧回放结果翻转为 {len(data['improvements_vs_previous'])} 好 {len(data['regressions_vs_previous'])} 坏，完整初态 {data['complete_initial_matches_with_previous']} 相同、{40-data['complete_initial_matches_with_previous']-data['complete_initial_unknown_with_previous']} 不同、{data['complete_initial_unknown_with_previous']} 缺失，差额不作纯选项收益或选择错误归因。",
        f"覆盖规则的子任务中双方全部失败 {len(failed)} 处，未知 {data['unknown_subtask_count']} 处；未覆盖规则的 {len(unsupported)} 局单列。",
        '本批只评测；新增公开锚点调用、额外采样及私有目标续接同时变化。未用 D2 调阈值，也未训练模型。',
        '',
        '| 整局臂 | 成功 | Wilson 95% |', '|---|---:|---:|',
        f"| 新 v7 独立回放 | {stats['success']}/40 | {interval(stats['wilson95'])} |",
        f"| 前版独立回放 | 23/40 | {interval(wilson(23, 40))} |",
        f"| 旧 schema6 模型 HTTP 闭环 | 10/40 | {interval(wilson(10, 40))} |",
        f"| A1-M | 28/40 | {interval(wilson(28, 40))} |", '',
        '采样包络按已测分支逐子任务择优，受先前选中路径限制；它不是部署策略的整局期望成功率，也不是穷举全部后继状态的数学上界。私有目标进展不进入公开请求或模型状态。未覆盖规则的整句 fallback 可有实际整局回放结果，但不能据此认证它的子任务采样上限。', '',
        f"本批采样成功而独立回放失败 {len(replay_gaps)} 局："+(', '.join(replay_gaps) or '无')+'。新批与历史十五条差异分开保留，不覆盖旧分数。', '',
        f"回放成功而采样包络为 False 的 {len(reverse_gaps)} 局："+(', '.join(reverse_gaps) or '无')+'。这也说明这里的采样包络并非数学上的整局上界。', '',
        '| 套件 | 原生回放 | Wilson 95% | 采样包络 | Wilson 95% | A1-M |',
        '|---|---:|---:|---:|---:|---:|']
    for suite, item in sorted(data['by_suite'].items()):
        replay = item['replay']
        lines.append(f"| {suite} | {replay['success']}/{replay['n']} | {interval(replay['wilson95'])} | {item['sampled_success']}/{item['sampled_known']} + {item['sampled_unknown']} unknown | {interval(item['sampled_wilson95'])} | {replay['A1_M_success_on_same_closed_cases']}/5 |")
    lines += ['', '下面按子任务类型汇总：进展是登记目标或局部子任务的私有诊断判据；local 和 native 另列。这里 native 是分支端点的环境终止信号，不是该方法从初态独立完成整局的成功率。重复试次及连续子任务不视为独立布局。', '',
        '| 子任务 | 方法 | 私有进展 | Wilson 95% | local | native |', '|---|---|---:|---:|---:|---:|']
    groups = defaultdict(list)
    for detail in details:
        for trial in detail['trials']:
            groups[(detail['subtask']['mode'], (trial.get('variant') or {}).get('name') or trial['method'])].append(trial)
    for (mode, method), trials in sorted(groups.items()):
        values = [t['private_progress_success'] for t in trials]
        known = [v for v in values if type(v) is bool]
        lines.append(f"| {mode} | {method} | {rate(values)} | {interval(wilson(sum(known), len(known)))} | {rate_ci([t['local_success'] for t in trials])} | {rate_ci([t['native_task_success'] for t in trials])} |")
    expanded = defaultdict(list)
    for detail in details:
        for trial in detail['trials']:
            expanded[(detail['suite'], detail['subtask']['mode'], trial['method'],
                      (trial.get('variant') or {}).get('name'))].append(trial)
    rates = []
    for (suite, mode, method, variant), trials in sorted(expanded.items(), key=lambda item: str(item[0])):
        rates.append({'suite': suite, 'mode': mode, 'method': method, 'variant': variant,
                      **{field: measured_rate([t[field] for t in trials])
                         for field in ('private_progress_success', 'local_success', 'native_task_success')}})
    (root/'measured_v7_D2_rates_expanded.json').write_text(json.dumps({
        'evaluation_only': True, 'training': False, 'rates': rates,
        'sampled_success_replay_failed_cases': replay_gaps,
        'scope': 'three predicates retained separately; repeated trials are not independent layouts'}, indent=2)+'\n')
    lines += ['', '[按套件 × 子任务 × 方法的三种判据统计及 Wilson 区间](measured_v7_D2_rates_expanded.json)保留全部分类。每个已覆盖子任务的逐方法进展次数如下；π 每变体三次，自有技能一次。各次种子、local/native、仿真步数、真实调用参数及原件引用见 [逐子任务记录](measured_v7_D2_subtasks.jsonl)。', '',
        '逐子任务 Wilson 95% 对照：0/3=0.0–56.1%，1/3=6.1–79.2%，2/3=20.8–93.9%，3/3=43.9–100.0%；0/1=0.0–79.3%，1/1=20.7–100.0%。', '',
        '| 局 / 子任务 | self | in_place | initial_pose | full_task | measured_anchor |', '|---|---:|---:|---:|---:|---:|']
    methods = ['self', 'in_place', 'initial_pose', 'full_task', 'measured_anchor']
    for detail in details:
        by_method = defaultdict(list)
        for t in detail['trials']:
            by_method[(t.get('variant') or {}).get('name') or t['method']].append(t['private_progress_success'])
        label = detail['subtask'].get('id', detail['subtask'].get('key', detail['subtask']['mode']))
        lines.append('| '+detail['case']+' / '+str(label)+' | '+' | '.join(rate(by_method[m]) if by_method[m] else '—' for m in methods)+' |')
    lines += ['', '| 双方均失败的子任务 | 记录的停止原因（次数） |', '|---|---|']
    for detail in failed:
        reasons = Counter(t['reason'] for t in detail['trials'])
        label = detail['subtask'].get('id', detail['subtask'].get('key', detail['subtask']['mode']))
        lines.append('| '+detail['case']+' / '+str(label)+' | '+', '.join(f'{k}: {n}' for k, n in reasons.most_common())+' |')
    audit_path = root/'measured_v7_D2_receipt_audit_both_failed_receipts.jsonl'
    if audit_path.exists():
        audited = [json.loads(line) for line in audit_path.read_text().splitlines()]
        lines += ['', '下面继续展开实际内部失败回执，而非只使用外层恢复预算标签；计数包含该分支内各次失败尝试，不能直接当作唯一物理根因。完整逐次证据见 [130分支回执](measured_v7_D2_receipt_audit_both_failed_receipts.jsonl)。', '',
            '| 局 / 子任务 | 自有技能内部失败 | π分支内部失败 |', '|---|---|---|']
        for detail in audited:
            counts = {'self': Counter(), 'call_vla': Counter()}
            for trial in detail['trials']:
                counts[trial['method']].update(trial['recorded_receipt_trace']['failure_receipts'])
            label = detail['case']+' / '+detail['subtask']['id']
            cells = [', '.join(f'{k}: {n}' for k, n in counts[m].most_common()) or '无失败回执（见外层停止原因及公开/私有判据）' for m in ('self', 'call_vla')]
            lines.append('| '+label+' | '+' | '.join(cells)+' |')
        lines += ['', '[本批7局回放差异的逐段回执](measured_v7_D2_receipt_audit_replay_gap_receipts.jsonl)保留实际调用参数、种子、源/目标ID、各段local/private/native结果和停止原因；只读提取，不重判。[提取manifest](measured_v7_D2_receipt_audit_manifest.json)保存SHA。']
    lines += ['', f"上述覆盖规则的 {len(details)} 个子任务共 {sum(len(d['trials']) for d in details)} 个分支；不含两处未覆盖规则的整句fallback调用。", '',
        '| 请求变体 | 分支数 | 实际进入π推理 | 未进入推理 |', '|---|---:|---:|---:|']
    call_counts = {(r['requested_variant'], r['measure']): r['n'] for r in data['requested_vs_actual_vla']}
    for variant in ('in_place', 'initial_pose', 'full_task', 'measured_anchor'):
        lines.append(f"| {variant} | {call_counts.get((variant, 'trials'), 0)} | {call_counts.get((variant, 'trials_reaching_policy'), 0)} | {call_counts.get((variant, 'trials_without_policy_inference'), 0)} |")
    lines += ['', '筛查拒绝不能自动称作真实碰撞或误杀；数值 IK 未找到解不能证明几何不可达；交还标签不能单独证明物体滑落。所有失败保留，未重跑闭合回合换分数。', '',
        '未覆盖规则的局：'+', '.join(r['case'] for r in unsupported)+'。具体规则见 [未覆盖清单](measured_v7_D2_unsupported_cases.jsonl)。', '',
        '[40 局逐对表](measured_v7_D2_comparison.md)保留与前版、模型及 A1 的逐局对照；[原始对照 JSONL](measured_v7_D2_comparison.jsonl)含每条 summary 的路径与 SHA。完整 A1 积分/控制器/RNG 初态仍缺，不把 EEF 相同视为完整初态相同。', '',
        '执行 Git tree `2db200134ea6689e36a66e8aee6f45daa8270b4e`；归档 SHA256 `7a08e6f42ad4b452d68f3b463cde883c2e0aeb20fe8ba9340ce2791d511ebcb2`；schema7 SHA256 `546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182`；contract SHA256 `a0fef7407efb67b4f9cde557cfa09ffcf3964eaaf9eaabad9f671d4e5b900f0b`。这些是实际执行快照，报告交付的 Git commit 另记。', '',
        '[登记 manifest](measured_v7_D2_manifest.json)、[完整分类与调用统计](measured_v7_D2_delivery_summary.json)、[逐次子任务](measured_v7_D2_subtasks.jsonl)、[双方均失败](measured_v7_D2_both_failed_subtasks.jsonl)均保留原件引用。公开执行与 efa 快照逐 blob 相同，仅私有阶段续接不同；N1/N2/155 回归见本目录对应报告。PRO、D2、确认状态不进训练。']
    (root/'MEASURED_V7_D2_40.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
