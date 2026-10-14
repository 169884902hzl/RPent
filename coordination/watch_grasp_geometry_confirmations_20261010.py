"""Close each registered confirmation once, preserving every physical failure."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENTS = ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1'
OUT = ROOT / 'coordination/grasp_geometry_confirmation_event_closed_20261010_r2'
CATEGORIES = ('bottle', 'bowl', 'box', 'cup', 'frypan')
ENV = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')


def summarize(parents, output):
    command = [str(ROOT / '.venv/bin/python'), '-m',
               'coordination.summarize_geometric_confirmation_r3_20261010']
    for parent in parents:
        command.extend(['--parent', str(parent)])
    command.extend(['--output', str(output)])
    subprocess.run(command, cwd=ROOT, env=ENV, check=True)


def main():
    OUT.mkdir(exist_ok=True)
    previous = None
    reported_failures = set()
    while True:
        progress = []
        for category in CATEGORIES:
            parent, output = PARENTS / category, OUT / category
            n = 0
            for path in parent.glob('job*/part*/probe/infrastructure_status.json'):
                try:
                    n += json.loads(path.read_text()).get('shard_completed_cases', 0)
                except json.JSONDecodeError:
                    continue
            progress.append({'category': category, 'recorded_n': n})
            submission = parent / 'preparation/formal_submission.json'
            if not submission.exists() or (output / 'manifest.json').exists():
                continue
            submitted = json.loads(submission.read_text())
            jobs = ','.join(submitted[key].split(';')[0]
                            for key in ('startup_job', 'formal_job'))
            status = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j', jobs,
                                             '-o', 'JobID,State,ExitCode'], text=True)
            states = [line.split('|') for line in status.splitlines() if line.strip()]
            if not all(any(s[0] == job or s[0].startswith(job + '_') for s in states)
                       for job in jobs.split(',')):
                continue
            failed = [s for s in states if s[1] in
                      ('FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY')]
            if failed:
                signature = tuple(tuple(s) for s in failed)
                if signature not in reported_failures:
                    print(json.dumps({'needs_infrastructure_repair': failed,
                                      'physical_failure_retries_allowed': False}), flush=True)
                    reported_failures.add(signature)
                resume_registration = parent / 'preparation/infrastructure_resume.json'
                if not resume_registration.exists():
                    continue
                registration = json.loads(resume_registration.read_text())
                resume_root = Path(registration['resume_root'])
                resume_formal = resume_root / 'preparation/formal_submission.json'
                if not resume_formal.exists():
                    continue
                resumed = json.loads(resume_formal.read_text())
                more = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j',
                    ','.join(resumed[k] for k in ('startup_job', 'formal_job')),
                    '-o', 'JobID,State,ExitCode'], text=True)
                more_states = [line.split('|') for line in more.splitlines() if line.strip()]
                if not all(any(s[0] == resumed[key] or s[0].startswith(resumed[key] + '_')
                               for s in more_states) for key in ('startup_job', 'formal_job')):
                    continue
                if not more_states or any(s[1] != 'COMPLETED' or s[2] != '0:0' for s in more_states):
                    continue
                valid = True
                for state in failed:
                    array, part = state[0].split('_')
                    directory = parent / ('job' + array) / ('part' + part)
                    runplan = json.loads((directory / 'run_manifest.json').read_text())
                    # The original array has eight shards; supplement shards
                    # do not determine its denominator or membership.
                    expected = {c['name'] for c in runplan['cases'][int(part)::submitted['formal_shards']]}
                    rows = [json.loads(line) for line in
                            (directory / 'probe/episodes.jsonl').read_text().splitlines()]
                    if {r['case']['name'] for r in rows} != expected:
                        valid = False
                    for row in rows:
                        if row.get('infrastructure_failure'):
                            if row.get('first_attempt') or row.get('error_stage') != 'startup':
                                valid = False
                        elif row.get('raised_error'):
                            valid = False
                if not valid:
                    raise ValueError('failed original shard is not explained only by startup faults')
            if not states or any(s[1] not in ('COMPLETED', 'FAILED') for s in states):
                continue
            summarize([parent], output)
            manifest = json.loads((output / 'manifest.json').read_text())
            result = manifest['groups'][category]
            if not result['complete']:
                raise ValueError('completed jobs lack registered confirmation records')
            m, public = result['success'], result['public_verifier']
            receipt = output / 'receipt.md'
            receipt.write_text(
                f'### Codex3：{category}独立扰动抓取确认（{manifest["generated_utc"]}）\n\n'
                f'注册{result["registered_n"]}、完整记录{result["recorded_n"]}；'
                f'锁定v3成功{m["k"]}/{m["n"]}，Wilson 95% '
                f'{m["wilson95"][0]:.1%}–{m["wilson95"][1]:.1%}。'
                f'公开一致{public["agreement_all_registered"]["k"]}/{m["n"]}；'
                f'FP/FN {public["fp"]}/{public["fn"]}，'
                f'已知真值公开缺测{public["public_null_on_known_truth"]}，'
                f'真值unknown{public["truth_unknown"]}，均保留注册分母。'
                f'单类内部门槛通过：{result["internal_class_thresholds_passed"]}。\n\n'
                f'基础设施故障唯一状态{result["infrastructure"]["unique_registered_cases"]["k"]}'
                f'/{result["registered_n"]}；按所有startup/formal及补测分片取并集，原故障仍计数。\n\n'
                f'逐次记录、来源和源码SHA：{output}/manifest.json；物理失败不补跑、'
                '不替换。整池永久排除训练。单类结果不代替五类总体判定；'
                '尚未冻结、未准入训练。\n')
            subprocess.run([str(ROOT / '.venv/bin/python'),
                str(ROOT / 'scripts/append_coordination_receipt_20261008.py'),
                '--coordination', '/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md',
                '--receipt', str(receipt)], cwd=ROOT, check=True)
        if progress != previous:
            print(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              'confirmation_progress': progress}), flush=True)
            previous = progress
        if all((OUT / category / 'manifest.json').exists() for category in CATEGORIES):
            summarize([PARENTS / category for category in CATEGORIES], OUT / 'fiveclass')
            return
        time.sleep(45)


if __name__ == '__main__':
    main()
