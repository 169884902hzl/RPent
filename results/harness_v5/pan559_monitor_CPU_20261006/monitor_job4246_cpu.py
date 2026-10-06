"""Read only the registered job4246 paths and preserve CPU snapshots."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
JOB = ROOT / 'results/harness_v5/pan556_coupled_lift_confirmation100/job4246'
BASE = Path(__file__).resolve().parent
MANIFEST = ROOT / 'results/harness_v5/pan556_coupled_lift_confirmation100_CPU_20261006/preparation/pan_coupled_lift_confirmation100.json'
MANIFEST_SHA = '32e11afe73db40727b6f9574e68be2127033c4fdd47f7ea355b3debe23987737'
STATISTIC = ROOT / 'scripts/summarize_v5_grasp543_20261006.py'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'{args}: {r.stderr}')
    return r.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out = BASE / ('final_' + now if args.final else now)
    out.mkdir(parents=True, exist_ok=False)
    assert sha(MANIFEST.read_bytes()) == MANIFEST_SHA
    plan = json.loads(MANIFEST.read_text())
    sacct = command(['sacct', '-j', '4246', '--format=JobID,JobIDRaw,State,ExitCode,Elapsed,NodeList', '-P'])
    squeue = command(['squeue', '-j', '4246', '-o', '%.18i %.9P %.30j %.8u %.2t %.10M %.6D %R'])
    (out / 'sacct.txt').write_text(sacct)
    (out / 'squeue.txt').write_text(squeue)
    jobs = [dict(zip(sacct.splitlines()[0].split('|'), line.split('|')))
            for line in sacct.splitlines()[1:] if line.strip()]
    array = [j for j in jobs if '.' not in j['JobID']]
    if args.final and (len(array) != 8 or any(j['State'] != 'COMPLETED' or j['ExitCode'] != '0:0' for j in array)):
        raise ValueError('Final report requires eight completed exit0 shards; no physical result is retried')
    cli = [str(ROOT / '.venv/bin/python'), str(STATISTIC), '--manifest', str(MANIFEST),
           '--manifest-sha256', MANIFEST_SHA, '--ledger-context', 'SOURCE556/job4246', MANIFEST_SHA]
    inputs, parts = [], []
    for part in range(8):
        d = JOB / f'part{part}'
        definitions = [
            ('episodes', d / 'probe/episodes.jsonl', '--ledger'),
            ('infrastructure_attempts', d / 'probe/infrastructure_attempts.jsonl', '--infrastructure-ledger'),
            ('case_infrastructure_events', d / f'infrastructure_cases_{MANIFEST_SHA}.jsonl', '--infrastructure-ledger'),
            ('preflight', d / 'preflight.json', None),
            ('summary', d / 'probe/summary.json', None),
            ('slurm_log', ROOT / f'results/slurm-4246_{part}.log', None),
        ]
        counts = {'part': part, 'planned': len(plan['cases'][part::8]), 'episodes': 0, 'infrastructure_attempts': 0}
        for kind, path, flag in definitions:
            ref = {'part': part, 'kind': kind, 'path': str(path), 'exists': path.is_file()}
            if path.is_file():
                data = path.read_bytes()
                dst = out / 'input_snapshot' / f'part{part}' / kind / path.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                ref.update(sha256=sha(data), bytes=len(data), snapshot_path=str(dst), snapshot_sha256=sha(data))
                if flag:
                    complete = data if data.endswith(b'\n') or not data else data[:data.rfind(b'\n') + 1]
                    if complete != data:
                        if args.final:
                            raise ValueError(f'Incomplete final ledger line: {path}')
                        readable = dst.with_name('complete_records.jsonl')
                        readable.write_bytes(complete)
                        ref.update(partial_tail_bytes=len(data) - len(complete), analysis_path=str(readable), analysis_sha256=sha(complete))
                    else:
                        readable = dst
                        ref['partial_tail_bytes'] = 0
                    if kind in counts:
                        counts[kind] = sum(bool(line.strip()) for line in complete.splitlines())
                    cli.extend([flag, str(path if args.final else readable)])
            elif flag:
                cli.extend([flag, str(path)])
            inputs.append(ref)
        parts.append(counts)
    cli.extend(['--output', str(out / 'statistic')])
    (out / 'summarizer_command.json').write_text(json.dumps(cli, indent=2) + '\n')
    stdout = command(cli)
    (out / 'summarizer_stdout.json').write_text(stdout)
    report = json.loads((out / 'statistic/report.json').read_text())
    summary = {
        'scope': 'Exact job4246 read-only CPU monitor; registered first physical outcomes preserved',
        'snapshot_time_utc': now, 'final': args.final, 'job': '4246',
        'manifest': {'path': str(MANIFEST), 'sha256': MANIFEST_SHA},
        'source': plan['source_snapshot'], 'statistic': report['producer'],
        'sacct': array, 'parts': parts, 'input_index': inputs,
        'observed_invocations': report['observed_invocations'],
        'first_physical_attempts': report['first_physical_attempts'],
        'complete_first_physical': report['complete_first_physical'],
        'metrics': report['by_manifest_condition_group'],
        'infrastructure': report['infrastructure_by_manifest'],
        'retry_policy_violations': report['retry_policy_violations'],
        'report': {'path': str(out / 'statistic/report.json'), 'sha256': sha((out / 'statistic/report.json').read_bytes())},
        'physical_trials_started_by_monitor': 0, 'new_training_rows': 0,
    }
    (out / 'monitor_report.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'out': str(out), 'sacct': array, 'parts': parts,
                     'observed_invocations': report['observed_invocations'],
                     'first_physical_attempts': report['first_physical_attempts'],
                     'infrastructure': summary['infrastructure'], 'report_sha256': summary['report']['sha256']}))


if __name__ == '__main__':
    main()
