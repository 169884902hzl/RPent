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
    lines = [
        f"恢复预算 1 档的 40 局采样与独立整局回放全部闭合；原生整局成功 {stats['success']}/40，Wilson 95% {interval(stats['wilson95'])}。",
        f"实测采样包络 {stats['sampled_bound_success']}/{stats['sampled_bound_known']}，另 {40-stats['sampled_bound_known']} 局私有规则未覆盖；已知分母的 Wilson 95% {interval(stats['sampled_bound_wilson95'])}。",
        f"前版回放 23/40、模型 10/40、A1-M 28/40；新旧回放结果翻转为 {len(data['improvements_vs_previous'])} 好 {len(data['regressions_vs_previous'])} 坏，完整初态仅 {data['complete_initial_matches_with_previous']}/40 认证相同，差额不作纯选项收益或选择错误归因。",
        f"覆盖规则的子任务中双方全部失败 {len(failed)} 处，未知 {data['unknown_subtask_count']} 处；未覆盖规则的 {len(unsupported)} 局单列。",
        '本批只评测；新增公开锚点调用、额外采样及私有目标续接同时变化。未用 D2 调阈值，也未训练模型。',
        '',
        '| 整局臂 | 成功 | Wilson 95% |', '|---|---:|---:|',
        f"| 新 v7 独立回放 | {stats['success']}/40 | {interval(stats['wilson95'])} |",
        f"| 前版独立回放 | 23/40 | {interval(wilson(23, 40))} |",
        f"| 旧 schema6 模型 HTTP 闭环 | 10/40 | {interval(wilson(10, 40))} |",
        f"| A1-M | 28/40 | {interval(wilson(28, 40))} |", '',
        '采样包络按已测分支逐子任务择优，受先前选中路径限制；它不是部署策略的整局期望成功率，也不是穷举全部后继状态的数学上界。私有目标进展不进入公开请求或模型状态。未覆盖规则的整句 fallback 可有实际整局回放结果，但不能据此认证它的子任务采样上限。', '',
        '| 套件 | 原生回放 | Wilson 95% | 采样包络 | Wilson 95% | A1-M |',
        '|---|---:|---:|---:|---:|---:|']
    for suite, item in sorted(data['by_suite'].items()):
        replay = item['replay']
        lines.append(f"| {suite} | {replay['success']}/{replay['n']} | {interval(replay['wilson95'])} | {item['sampled_success']}/{item['sampled_known']} + {item['sampled_unknown']} unknown | {interval(item['sampled_wilson95'])} | {replay['A1_M_success_on_same_closed_cases']}/5 |")
    lines += ['', '下面按子任务类型汇总：进展是登记目标或局部子任务的私有诊断判据；local 和 native 另列。重复试次及连续子任务不视为独立布局。', '',
        '| 子任务 | 方法 | 私有进展 | Wilson 95% | local | native |', '|---|---|---:|---:|---:|---:|']
    groups = defaultdict(list)
    for detail in details:
        for trial in detail['trials']:
            groups[(detail['subtask']['mode'], (trial.get('variant') or {}).get('name') or trial['method'])].append(trial)
    for (mode, method), trials in sorted(groups.items()):
        values = [t['private_progress_success'] for t in trials]
        known = [v for v in values if type(v) is bool]
        lines.append(f"| {mode} | {method} | {rate(values)} | {interval(wilson(sum(known), len(known)))} | {rate([t['local_success'] for t in trials])} | {rate([t['native_task_success'] for t in trials])} |")
    lines += ['', '每个已覆盖子任务的逐方法进展次数如下；π 每变体三次，自有技能一次。各次种子、local/native、仿真步数、真实调用参数及原件引用见 [逐子任务记录](measured_v7_D2_subtasks.jsonl)。', '',
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
    lines += ['', '筛查拒绝不能自动称作真实碰撞或误杀；数值 IK 未找到解不能证明几何不可达；交还标签不能单独证明物体滑落。所有失败保留，未重跑闭合回合换分数。', '',
        '未覆盖规则的局：'+', '.join(r['case'] for r in unsupported)+'。具体规则见 [未覆盖清单](measured_v7_D2_unsupported_cases.jsonl)。', '',
        '[40 局逐对表](measured_v7_D2_comparison.md)保留与前版、模型及 A1 的逐局对照；[原始对照 JSONL](measured_v7_D2_comparison.jsonl)含每条 summary 的路径与 SHA。完整 A1 积分/控制器/RNG 初态仍缺，不把 EEF 相同视为完整初态相同。', '',
        '执行 Git tree `2db200134ea6689e36a66e8aee6f45daa8270b4e`；归档 SHA256 `7a08e6f42ad4b452d68f3b463cde883c2e0aeb20fe8ba9340ce2791d511ebcb2`；schema7 SHA256 `546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182`；contract SHA256 `a0fef7407efb67b4f9cde557cfa09ffcf3964eaaf9eaabad9f671d4e5b900f0b`。这些是实际执行快照，报告交付的 Git commit 另记。', '',
        '[登记 manifest](measured_v7_D2_manifest.json)、[完整分类与调用统计](measured_v7_D2_delivery_summary.json)、[逐次子任务](measured_v7_D2_subtasks.jsonl)、[双方均失败](measured_v7_D2_both_failed_subtasks.jsonl)均保留原件引用。公开执行与 efa 快照逐 blob 相同，仅私有阶段续接不同；N1/N2/155 回归见本目录对应报告。PRO、D2、确认状态不进训练。']
    (root/'MEASURED_V7_D2_40.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
