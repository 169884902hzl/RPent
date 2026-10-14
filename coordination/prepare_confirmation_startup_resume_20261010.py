"""Supplement startup-only faults on the exact registered states and methods."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1/bowl'
OUT = ROOT / 'results/harness_v5/grasp_confirmation_startup_resume_20261010_r1/bowl'
FAULTS = ROOT / 'coordination/confirmation_env_reset_faults_20261010_r1.json'
RESET = ROOT / 'coordination/confirmation_env_reset_probe_20261010_r1/records.json'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent_plan = PARENT / 'preparation/confirmation.json'
    original = json.loads(parent_plan.read_text())
    names = {fault['case'] for fault in json.loads(FAULTS.read_text())}
    resets = {r['case']: r for r in json.loads(RESET.read_text())}
    if any(resets[name]['status'] != 'reset_pass' or resets[name]['controller_skill_executed']
           or resets[name]['registered_restore']['restore_max_absolute_error'] != 0 for name in names):
        raise ValueError('startup fault not independently recovered')
    faults = []
    for fault in json.loads(FAULTS.read_text()):
        path = Path(fault['input'])
        row = json.loads(path.read_text().splitlines()[fault['line'] - 1])
        if (row['case']['name'] not in names or not row.get('infrastructure_failure')
                or row.get('first_attempt') or row.get('error_stage') != 'startup'):
            raise ValueError('physical attempts must never be supplemented')
        faults.append({**fault, 'input_sha256': pin(path)['sha256'],
                       'error': row.get('raised_error'), 'no_first_physical_attempt': True})
    plan = copy.deepcopy(original)
    plan['cases'] = [c for c in original['cases'] if c['name'] in names]
    if len(plan['cases']) != len(names):
        raise ValueError('fault not in registered confirmation')
    prep = OUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    plan.update(producer=pin(producer), qualification_authorized=False,
                startup_infrastructure_supplement=True,
                original_confirmation_plan=pin(parent_plan),
                startup_faults=faults, startup_recovered_reset_evidence=pin(RESET))
    plan['producer_dependencies'].append(pin(producer))
    plan['references'].extend([pin(parent_plan), pin(FAULTS), pin(RESET)])
    path = prep / 'confirmation.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=plan['source_path'], PERTURB_SKILL_ADAPTER=plan['adapter_path'],
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    checked = subprocess.run(['bash', str(LAUNCH)], env=env, cwd='/tmp', capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    registration = {'plan': pin(path), 'parent': str(PARENT), 'registered_n': len(names),
        'original_confirmation_plan': pin(parent_plan), 'faults': faults,
        'public_controls_and_v3_unchanged': True, 'physical_failures_retried': False,
        'source_identity': pin(Path(plan['source_path']) / 'source_identity_v3r9.json'),
        'launcher': pin(LAUNCH), 'reset_evidence': pin(RESET), 'training_allowed': False,
        'CPU_preflight': checked.stdout, 'startup_job': None, 'formal_job': None}
    receipt = prep / 'registration.md'
    receipt.write_text('### Codex3：碗确认启动故障补测预登记\n\n'
        f'仅补测2条从未执行抓取的状态，原状态哈希、公开控制、验证器及v3源码不变：{path}。'
        '原两次startup超时、退出码和全部原始记录保留。独立GPU reset诊断恢复耗时6.91/6.16秒，'
        '恢复误差均0，未执行技能；根因暂归为可恢复环境启动故障，具体底层延迟未定位。'
        '本次补测不是物理失败重试；注册分母仍100，不增加或替换状态，补测失败照实保留。'
        '全部布局永久排除训练。\n')
    subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'scripts/append_coordination_receipt_20261008.py'),
        '--coordination', '/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md',
        '--receipt', str(receipt)], cwd=ROOT, check=True)
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                                env=env, capture_output=True, text=True, check=True)
    registration['startup_job'] = submitted.stdout.strip().split(';')[0]
    (prep / 'submission.json').write_text(json.dumps(registration, indent=2) + '\n')
    (PARENT / 'preparation/infrastructure_resume.json').write_text(
        json.dumps({**registration, 'resume_root': str(OUT)}, indent=2) + '\n')
    print(json.dumps(registration), flush=True)


if __name__ == '__main__':
    main()
