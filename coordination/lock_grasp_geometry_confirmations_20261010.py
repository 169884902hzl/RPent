"""Lock complete class methods, register unused states, then submit startups."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
COORDINATION = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
LAUNCHER = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
OUT = ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1'
POOL = ROOT / 'results/harness_v5/perturb_skill_confirmation_geometry_20261009_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection-report', type=Path, required=True)
    parser.add_argument('--category', action='append',
        choices=('bottle', 'bowl', 'box', 'cup', 'frypan'))
    args = parser.parse_args()
    prepare_lock = (ROOT / 'coordination/grasp_confirmation_prepare.lock').open('a')
    fcntl.flock(prepare_lock, fcntl.LOCK_EX)
    evidence = args.selection_report / 'manifest.json'
    report = json.loads(evidence.read_text())
    # Both physical performance and an informative public receipt matter at
    # runtime. Rank complete packages by their smaller normalized objective;
    # no selection score is an additional admission gate. Confirmation alone
    # applies the registered thresholds.
    def rank(item):
        group, value = item
        physical = value['v3_success']['rate']
        public = value['public_verifier']['agreement_all_registered']['rate']
        return min(physical / .90, public / .95), physical, public, group

    selected = {}
    for category in args.category or ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        if (OUT / category / 'preparation/submission.json').exists():
            continue
        options = [(g, v) for g, v in report['groups'].items() if v['type'] == 'grasp_' + category]
        selected[category] = max(options, key=rank)
    if not selected:
        print(json.dumps({'all_requested_categories_already_registered': True}), flush=True)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for category, (group, value) in selected.items():
        path = Path(value['plan']['path'])
        if pin(path)['sha256'] != value['plan']['sha256']:
            raise ValueError('selection plan changed before locking')
        destination = OUT / category / 'preparation'
        command = [sys.executable, '-m', 'coordination.prepare_grasp_geometry_confirmation_20261010',
            '--parent-plan', str(path), '--pool', str(POOL / ('grasp_' + category + '_combined.json')),
            '--selection-evidence', str(evidence), '--selection-states',
            str(ROOT / 'coordination/servo_only_fiveclass_paired_closed_20261010_r4/rows.jsonl'),
            '--launcher', str(LAUNCHER), '--output', str(destination)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (OUT / (category + '_preparation.log')).write_text(result.stdout + result.stderr)
        result.check_returncode()
        records.append({'category': category, 'selection_group': group,
            'selection_v3_success': value['v3_success'],
            'selection_public_agreement': value['public_verifier']['agreement_all_registered'],
            'method_plan': pin(path), 'confirmation_plan': pin(destination / 'confirmation.json'),
            'source_identity': value['source_identity'], 'producer': pin(Path(__file__)),
            'ranking': rank((group, value))})
    locked = {'selection_evidence': pin(evidence), 'methods': records, 'launcher': pin(LAUNCHER),
        'selection_rule': 'maximize min(v3_success/.90,public_agreement/.95), then v3, then agreement; complete configurations only',
        'selection_score_is_not_an_admission_gate': True,
        'internal_thresholds': {'overall_success': .95, 'class_success': .90, 'public_agreement': .95},
        'registered_n': 100 * len(records), 'confirmation_outcomes_read_before_locking': False,
        'permanent_training_exclusion': True, 'training_allowed': False}
    batch = '_'.join(selected)
    lock = OUT / ('method_lock_' + batch + '.json')
    if lock.exists():
        raise ValueError('method lock already exists; inspect preserved registration')
    lock.write_text(json.dumps(locked, indent=2) + '\n')
    receipt = OUT / ('registration_' + batch + '.md')
    receipt.write_text('### Codex3：扰动抓取独立确认预登记（' + batch + '）\n\n'
        + '方法、源码与每类按登记顺序取出的 100 个未执行状态已经锁定：' + str(lock)
        + '，SHA ' + pin(lock)['sha256'] + '。选择只使用完整方法配置，不拼接执行器与其他验证器。'
        + '选择规则同时考虑物理成功与公开一致，不增加选择批准入门。确认门槛仍为内部门槛：'
        + '总体≥95%、单类≥90%、验证器一致≥95%。unknown、绑定失败、公开缺测保留分母；'
        + '确认物理失败不补跑、不择优替换。整池布局参数/种子永久排除训练。'
        + '每类先用同源码同 launcher 完成一次真实启动，再释放余下99次。'
        + '当前预登记完成，尚无确认成绩，未冻结、未准入训练。\n')
    subprocess.run(['python3', str(ROOT / 'scripts/append_coordination_receipt_20261008.py'),
        '--coordination', str(COORDINATION), '--receipt', str(receipt)], cwd=ROOT, check=True)
    for record in records:
        path = Path(record['confirmation_plan']['path'])
        plan = json.loads(path.read_text())
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path),
            PERTURB_SKILL_PLAN_SHA=record['confirmation_plan']['sha256'],
            PERTURB_SKILL_SOURCE=plan['source_path'], PERTURB_SKILL_ADAPTER=plan['adapter_path'],
            PERTURB_SKILL_OUTPUT=str(path.parent.parent), PERTURB_SKILL_STARTUP='1',
            PERTURB_SKILL_CPU_ONLY='0')
        result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCHER)],
            env=env, capture_output=True, text=True, check=True)
        submission = {'name': record['category'], 'startup_job': result.stdout.strip(),
            'plan': record['confirmation_plan'], 'launcher': pin(LAUNCHER),
            'method_lock': pin(lock), 'qualification_allowed': True, 'training_allowed': False,
            'private_truth_rule_unchanged': True}
        (path.parent / 'submission.json').write_text(json.dumps(submission, indent=2) + '\n')
        print(json.dumps(submission), flush=True)


if __name__ == '__main__':
    main()
