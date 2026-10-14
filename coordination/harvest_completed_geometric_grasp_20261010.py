"""Close each completed physical method independently and publish exact pairs."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASES = [ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r8',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r9',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r10',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r11',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r12',
         ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r13']
OUT = ROOT / 'coordination/geometric_methods_event_closed_20261010_r1'
BEFORE = ROOT / 'coordination/servo_only_fiveclass_paired_closed_20261010_r4'
BASELINE = ROOT / 'artifacts/contact_methods_intermediate_20261009_r14/attempts.jsonl'
COORDINATION = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
ENV = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')


def run(*args):
    result = subprocess.run([str(ROOT / '.venv/bin/python'), *args], cwd=ROOT, env=ENV,
                            capture_output=True, text=True)
    result.check_returncode()
    return result.stdout


def publish(report, comparison, parent):
    d = json.loads((comparison / 'manifest.json').read_text())
    group, value = next(iter(d['groups'].items()))
    m = value['v3_success_all_registered']
    c = value['public_verifier_recorded']
    a, t = c['agreement_all_registered'], value['pair_transitions']
    lo, hi = m['wilson95']
    identity = value['source_identity']
    receipt = report / 'receipt.md'
    receipt.write_text(f'''### Codex3：{group} 选择批闭合（{datetime.datetime.now(datetime.timezone.utc).isoformat()}）

注册 {value['registered_n']}、完整物理记录 {value['recorded_n']}、未完成 {value['pending_n']}；锁定 v3 成功 {m['k']}/{m['n']}，Wilson 95% {lo:.1%}–{hi:.1%}，真值 unknown {value['v3_truth_unknown']}。公开一致 {a['k']}/{a['n']}，FP/FN {c['fp']}/{c['fn']}；已知真值的公开缺测 {c['public_null_on_known_truth']}，全部缺测保留分母。相对同状态新 v3 修前：改善 {t.get('improved', 0)}、退步 {t.get('regressed', 0)}、unknown 配对 {t.get('unknown_in_pair', 0)}。

逐次记录、失败类别、源码文件SHA及两方向误判：{comparison}。物理输入完整闭合副本：{report}。源码 identity：{identity['path']}，SHA {identity['sha256']}。修前来自相同状态纯伺服重放，π0.5 对照属于跨方法比较；旧 exclusive-v2 另列，不覆盖。

本批仍是选择/开发诊断，不是独立确认。内部门槛维持单类≥90%、总体≥95%、验证器一致≥95%；未冻结、未准入训练。所有注册失败/unknown 保留；不读取 PRO、不将私有真值用于运动或公开验证。父计划：{parent}。
''')
    result = subprocess.run(['python3', str(ROOT / 'scripts/append_coordination_receipt_20261008.py'),
        '--coordination', str(COORDINATION), '--receipt', str(receipt)], cwd=ROOT,
        capture_output=True, text=True, check=True)
    (report / 'publication.json').write_text(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(), 'stdout': result.stdout}, indent=2)+'\n')
    print(json.dumps({'closed': group, 'v3': m, 'agreement': a, 'pairs': t}), flush=True)


def main():
    OUT.mkdir(exist_ok=True)
    while True:
        parents = [p.parent.parent for base in BASES for p in sorted(base.glob('*/preparation/submission.json'))
                   if not (p.parent / 'superseded_submission.json').exists()]
        completed = 0
        for parent in parents:
            name = parent.name
            report = OUT / (parent.parent.name + '__' + name)
            comparison = report.with_name(report.name + '__vs_servo')
            formal = parent / 'preparation/formal_submission.json'
            if not formal.exists():
                continue
            submission = json.loads(formal.read_text())
            plan = json.loads(Path(submission['plan']['path']).read_text())
            if not report.exists():
                jobs = [submission['startup_job'].split(';')[0], submission['formal_job'].split(';')[0]]
                status = subprocess.run(['sacct', '-X', '-n', '-P', '-j', ','.join(jobs),
                    '-o', 'JobID,State,ExitCode'], capture_output=True, text=True, check=True).stdout
                states = [line.split('|') for line in status.splitlines() if line.strip()]
                if not states or any(row[1] != 'COMPLETED' or row[2] != '0:0' for row in states):
                    continue
                run('-m', 'coordination.pair_r14_grasp_repairs_20261010', '--baseline', str(BASELINE),
                    '--root', str(parent.parent), '--method', name, '--output', str(report))
                groups = json.loads((report / 'manifest.json').read_text())['groups']
                if len(groups) != 1 or next(iter(groups.values()))['pending_n'] != 0:
                    raise ValueError('completed job does not contain every registered physical case')
            if not comparison.exists():
                run('-m', 'coordination.compare_registered_grasp_methods_20261010', '--before', str(BEFORE),
                    '--input', str(report), '--output', str(comparison))
            if not (report / 'publication.json').exists():
                publish(report, comparison, plan.get('parent_plan'))
            completed += 1
            # Direct comparisons for isolated repair hypotheses are added only
            # when the entire parent method has closed, never from a prefix.
            previous = Path(plan['parent_plan']['path']).parent.parent if plan.get('parent_plan') else None
            direct = report.with_name(report.name + '__vs_parent')
            if previous and not direct.exists():
                parent_report = (ROOT / 'coordination/geometric_grasp_first_round_closed_20261010_r1'
                    if previous.parent.name == 'geometric_grasp_selection_20261010_r3' else
                    ROOT / 'coordination/geometric_grasp_coherent_closed_20261010_r4'
                    if previous.parent.name == 'geometric_grasp_selection_20261010_r5' else
                    ROOT / 'coordination/geometric_grasp_second_round_r4_closed_20261010_r2'
                    if previous.parent.name == 'geometric_grasp_selection_20261010_r4' else
                    BEFORE if previous.parent.name == 'servo_only_fiveclass_selection_20261010_r1' else
                    OUT / (previous.parent.name + '__' + previous.name))
                if (parent_report / 'rows.jsonl').exists():
                    run('-m', 'coordination.compare_registered_grasp_methods_r2_20261010', '--before', str(parent_report),
                        '--before-group', previous.parent.name + '/' + previous.name,
                        '--input', str(report), '--output', str(direct))
        if parents and completed == len(parents):
            print(json.dumps({'all_registered_methods_closed': completed}), flush=True)
            return
        time.sleep(30)


if __name__ == '__main__':
    main()
