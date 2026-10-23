"""Build the final paired evaluation report only from strict closed manifests."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def metric(value):
    ci = value['wilson95']
    return f"{value['success']}/{value['n']}" + (f"（95% {100*ci[0]:.1f}%–{100*ci[1]:.1f}%）" if ci else '')


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    closed = a.run/'CPU_closed40_final'
    default = a.run/'CPU_pi_default_closed46'
    summary = json.loads((closed/'manifest.json').read_text())
    default_summary = json.loads((default/'manifest.json').read_text())
    assert not summary['pending'] and summary['continuation_closed'] == 24
    assert not default_summary['pending'] and default_summary['closed_arms'] == 46
    proof = json.loads((a.run/'CPU_first_end_to_oracle_initial_physics_r2.json').read_text())
    assert proof['n'] == proof['matches'] == 24
    defaults = {row['case']: row for row in read_rows(default/'paired_cases.jsonl')}
    rows = read_rows(closed/'paired_cases.jsonl')
    for row in rows:
        other = defaults[row['case']]
        assert row['initial_physics_sha256'] == other['initial_physics_sha256']
        row['pi_default_success'] = other['pi_default_success']
        row['pi_default'] = other['pi_default']
    continuations = [row for row in rows if row['pi_then_oracle']]
    comparisons = {}
    for name in ('pi_only_success', 'oracle_from_start_success'):
        comparisons[name] = {
            'improved': sum(row['pi_then_oracle_replay_success'] and not row[name] for row in rows),
            'regressed': sum(row[name] and not row['pi_then_oracle_replay_success'] for row in rows)}
    costs = {}
    for field in ('replay_sim_steps', 'replay_decisions', 'replay_vla_inference_calls', 'independent_replay_wall_s'):
        values = [row['pi_then_oracle'][field] for row in continuations]
        costs[field] = {'median': median(values), 'sum': sum(values), 'n': len(values)}
    kinds = Counter(row['pi_then_oracle']['status'] for row in continuations)
    totals = summary['D2']
    text = [
        '# 同初态 D2：模型闭环与先 π 后选择', '',
        '40 局全部闭合；PRO/D2 只用于评测，不训练，不据此调整阈值。', '',
        '| 方法 | 实际整局回放 |', '|---|---:|',
        *[f'| {label} | {metric(totals[key])} |' for label, key in (
            ('只用 π，失败重试一次', 'pi_only_success'), ('旧模型 A（合法集 4）', 'v_next_a_success'),
            ('模型 B（合法集 5）', 'v_next_b_success'), ('开局 oracle', 'oracle_from_start_success'),
            ('先 π，失败后 oracle', 'pi_then_oracle_replay_success'))],
        f"| Codex2 登记的 π 默认模式 | {metric(default_summary['D2'])} |", '',
        'π 首次成功的 16 局保留；首次失败 24 局从第一次调用结束时的完整终态开始。',
        f"在这 24 局上，独立整局回放为 {metric(summary['first_failure24']['pi_then_oracle_replay_success'])}；有限分叉采样为 {metric(summary['first_failure24']['pi_then_oracle_sampled_success'])}。", '',
        f"合成 40 局的有限分叉采样为 {metric(totals['pi_then_oracle_sampled_success'])}，另 {totals['pi_then_oracle_sampled_success']['unknown_or_pending']} 局规则 unknown。unknown 不记失败、不从实际回放分母中删去。采样择优含未来分支结果，不是可执行模型分数。", '',
        '续接仍使用原整局 10000 仿真步预算的剩余量，未重给预算。恢复预算 1 从 π 首次失败之后开始；该诊断允许后续多次调用 π，因此与纯 π 只再试一次的调用次数不等。回放成本不含为 oracle 选路所做的额外采样搜索。', '',
        '24/24 续接回合初态 SHA 与保存的原首次终态相同：20 局同种子首试重现，4 局重放原留存控制与交还动作，后者公开轨迹最大误差为 0。',
        f"独立回放自身日志中 {summary['replay_initial_sha_serialized_and_matching']} 局序列化了初态 SHA，全部与首次终态相同；另外 {len(summary['replay_initial_sha_not_serialized'])} 局未序列化该字段，不额外声称完成了此项核验（名单见 manifest）。", '',
        '模型 B 与纯 π 的 46 臂完整初态一致，所有请求 human_available=false，oracle_choices_used=0。旧模型合法集 4、本次合法集 5；schema human 字段、编码容量和上下文长度也变了，不能把差额全归给权重。', '',
        'π 默认模式按 Codex2 登记使用模型 A 权重、固定训练域 delta=2。它是偏好策略，实际首个动作整句调用 5/40、子任务调用 32/40、自有动作 3/40，不是强制先整句调用。未改模式、未在 D2 调阈值。', '',
        '原版 6 臂：纯 π 6/6，模型 B 1/6，π 默认模式 4/6；是 3 个独立初态各 K1/K4，不视为 6 个独立布局。', '',
        '接近路径诊断未达到部署条件：修复高位路线仅 3/30 通过筛查并执行，0/3 到位，0/3 新增或加深接触；27 个零步拒绝不算安全成功。直线无否决为 6/30 到位、11/30 在 1 µm 口径有接触、2/30 在 1 mm 口径有接触。因此未接入生产，条件性的 N2/155 新路径重跑未进行。详见 APPROACH_CONTACT_RESULT.md。', '',
        '执行源码树：模型 4718f24e61851aacd10ee25a0f9818d550b61a53；续接 oracle f6ce1d46edd6396b9907ef529684a7dd099a7c30；路径诊断 67df3985d499846f6efc3312f1215173579fa840。', '',
        '逐局表见 paired_table.md；JSONL 保留原件路径、SHA、续接成本和未知原因。', '']
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'RESULTS.md').write_text('\n'.join(text))
    fields = ('pi_only_success', 'v_next_a_success', 'v_next_b_success', 'pi_default_success',
        'oracle_from_start_success', 'pi_then_oracle_replay_success', 'pi_then_oracle_sampled_success')
    table = ['| 场景 | 只用π | 模型A | 模型B | π默认 | 开局oracle | π后回放 | π后采样 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        table.append('| '+row['case']+' | '+' | '.join('?' if row[k] is None else str(int(row[k])) for k in fields)+' |')
    (a.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    (a.output/'paired_cases.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
    evidence = {'sources': [reference(closed/'manifest.json'), reference(default/'manifest.json'),
        reference(a.run/'CPU_first_end_to_oracle_initial_physics_r2.json')],
        'pi_then_oracle_vs_baselines': comparisons, 'continuation_costs': costs,
        'continuation_statuses': dict(kinds), 'training': False, 'evaluation_only': True}
    (a.output/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps({'comparisons': comparisons, 'costs': costs}))


if __name__ == '__main__':
    main()
