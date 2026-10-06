"""Summarize only the explicit registered drawer571/job4327 paths on CPU."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = Path(__file__).resolve().parent
MANIFEST = ROOT / 'results/harness_v5/drawer571_frontmost_clearance_CPU_20261006/preparation/drawer571_same20_frontmost_clearance.json'
MANIFEST_SHA = 'c0e2653e6e1046d56f3c223a9eec490b3653aad42e356b6f1a82a06f86c0a7b7'
SOURCE = ROOT / 'source_v5_drawer571_20261006'
JOB = ROOT / 'results/harness_v5/drawer571_frontmost_clearance_CPU_20261006/physical_same20/job4327'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args):
    result = subprocess.run(args, cwd=SOURCE, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{args}: {result.stderr}')
    return result.stdout


def accounting(stage):
    motions = (stage or {}).get('motion_evidence', [])
    chunks = [m for m in motions if m.get('name') == 'vla_act_chunk']
    return {'vla_chunks': len(chunks),
            'vla_requested_controls': sum(m.get('requested_action_count', 0) for m in chunks),
            'vla_executed_controls': sum(m.get('executed_action_count', 0) for m in chunks),
            'short_chunks': sum(m.get('executed_action_count', 0) < m.get('requested_action_count', 0) for m in chunks),
            'non_vla_executed_controls': sum(m.get('executed_action_count', m.get('steps_used', 0))
                                              for m in motions if m.get('name') != 'vla_act_chunk')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out = BASE / (('final_' if args.final else '') + now)
    out.mkdir(parents=True, exist_ok=False)
    if sha(MANIFEST) != MANIFEST_SHA:
        raise ValueError('Registered selection manifest changed')
    plan = json.loads(MANIFEST.read_text())
    source = plan['source_snapshot']
    for ref in [*source['files'], source['archive']]:
        if sha(Path(ref['path'])) != ref['sha256']:
            raise ValueError(f"Immutable source changed: {ref['path']}")
    sacct = command(['sacct', '-j', '4327', '--format=JobID,JobIDRaw,State,ExitCode,Elapsed,NodeList', '-P'])
    squeue = command(['squeue', '-j', '4327', '-o', '%.18i %.9P %.30j %.8u %.2t %.10M %.6D %R'])
    (out / 'sacct.txt').write_text(sacct)
    (out / 'squeue.txt').write_text(squeue)
    states = [dict(zip(sacct.splitlines()[0].split('|'), line.split('|')))
              for line in sacct.splitlines()[1:] if line.strip() and '.' not in line.split('|')[0]]
    if args.final and (len(states) != 8 or any(s['State'] != 'COMPLETED' or s['ExitCode'] != '0:0' for s in states)):
        raise ValueError('Final completion requires eight completed exit0 shards')
    cli = [str(ROOT / '.venv/bin/python'), '-m', 'scripts.summarize_v5_skill543_selection_20261006',
           '--manifest', str(MANIFEST), '--source-snapshot', str(SOURCE),
           '--source-commit', source['commit'], '--job-id', '4327', '--output-dir', str(out / 'statistic')]
    original_refs = []
    for part in range(8):
        for flag, path in [('--ledger', JOB / f'part{part}/episodes.jsonl'),
                           ('--infrastructure-ledger', JOB / f'part{part}/infrastructure_attempts.jsonl')]:
            cli.extend([flag, str(path)])
        for role, path in [('preflight', JOB / f'preflight_part{part}.json'),
                           ('infrastructure_status', JOB / f'part{part}/infrastructure_status.json'),
                           ('slurm_log', ROOT / f'results/slurm-4327_{part}.log')]:
            ref = {'part': part, 'role': role, 'path': str(path), 'exists': path.is_file()}
            if path.is_file():
                data = path.read_bytes()
                ref.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
                if role != 'slurm_log':
                    destination = out / 'status_inputs' / f'part{part}' / path.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
                    ref['snapshot'] = str(destination)
            original_refs.append(ref)
    shared = JOB / f'infrastructure_cases_{MANIFEST_SHA}.jsonl'
    cli.extend(['--infrastructure-ledger', str(shared)])
    (out / 'summarizer_command.json').write_text(json.dumps(cli, indent=2) + '\n')
    stdout = command(cli)
    (out / 'summarizer_stdout.json').write_text(stdout)
    report = json.loads((out / 'statistic/report.json').read_text())
    diagnostics = {r['case']: r for r in map(json.loads, (out / 'statistic/case_diagnostics.jsonl').read_text().splitlines())}
    groups, records, anomalies = defaultdict(Counter), [], []
    for ref in report['original_explicit_inputs']:
        if ref['role'] != 'ledger' or not ref.get('exists'):
            continue
        for line_no, line in enumerate(Path(ref['snapshot']).read_text().splitlines(), 1):
            row = json.loads(line)
            case, first = row['case'], row.get('first_attempt') or {}
            controls = accounting(first)
            setup_controls = [accounting(s) for s in row.get('setup', [])]
            server = row.get('server_chunk_execution') or {}
            chunks = [m for m in first.get('motion_evidence', []) if m.get('name') == 'vla_act_chunk']
            actual_prompts = sorted({m.get('instruction') for m in chunks if isinstance(m.get('instruction'), str)})
            observed_motion = first.get('physically_executed') is True or controls['vla_executed_controls'] + controls['non_vla_executed_controls'] > 0
            setup_legacy = [s.get('private_true_sustained_grasp') for s in row.get('setup', [])]
            setup_v2 = [(s.get('private_hold_truth_v2') or {}).get('success') for s in row.get('setup', [])]
            diagnostic = diagnostics[case['name']]
            item = {'case': case['name'], 'episode': case['episode'], 'type': case['type'],
                    'state_sha256': case['state_sha256'], 'attempt_index': row.get('attempt_index'),
                    'original_ledger': ref['path'], 'captured_ledger': ref['snapshot'], 'line': line_no,
                    'status': row['status'], 'infrastructure_failure': diagnostic['infrastructure_result'],
                    'first_stage_recorded_physical': first.get('physically_executed'),
                    'first_stage_observed_motion': observed_motion,
                    'private_before': first.get('private_before'), 'private_after': first.get('private_after'),
                    'public_verdict': first.get('receipt', {}).get('articulate_verified'),
                    'public_contact_stop': first.get('receipt', {}).get('stop') == 'measured_fixture_endpoint',
                    'recorded_contact_stop': first.get('receipt', {}).get('stop'),
                    'first_controls': controls, 'setup_controls': setup_controls,
                    'server_chunk_execution': server, 'registered_prompt': case['subtask_prompt'],
                    'recorded_chunk_prompts': actual_prompts,
                    'registered_prompt_match': actual_prompts == [case['subtask_prompt']] if chunks else None,
                    'registered_setup_count': len(case.get('setup', [])), 'observed_setup_count': len(row.get('setup', [])),
                    'setup_truth_legacy': setup_legacy, 'setup_truth_v2': setup_v2,
                    'root_cause_category': diagnostic['root_cause_category'],
                    'contact_budget_exhausted': diagnostic['contact_budget_exhausted'],
                    'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'), 'sha256': row.get('choices_sha256')},
                    'attempts': row.get('attempts', []), 'physical_failures_retried': row.get('physical_failures_retried')}
            records.append(item)
            group = groups[case['type']]
            group['recorded_cases'] += 1
            group['physical_first_observed_including_infrastructure'] += observed_motion
            group['zero_physical_first_records'] += not observed_motion
            group['requested_setup_stages'] += len(case.get('setup', []))
            group['recorded_setup_stages'] += len(row.get('setup', []))
            group['cases_without_registered_setup'] += not case.get('setup')
            group['budget_exhausted_cases'] += diagnostic['contact_budget_exhausted']
            group['public_contact_stop_cases'] += item['public_contact_stop']
            group['invalid5control_chunks'] += sum(m.get('requested_action_count') != 5 or m.get('executed_action_count') != 5 for m in chunks)
            for k, v in controls.items():
                group[k] += v
            group['complete5controls_each_chunk_first_cases'] += 0 < controls['vla_chunks'] <= 160 and all(m.get('requested_action_count') == m.get('executed_action_count') == 5 for m in chunks)
            group['server_requested_controls'] += server.get('requested_controls', 0)
            group['server_executed_controls'] += server.get('executed_controls', 0)
            group['server_external_truncation_cases'] += server.get('external_truncation') is True
            group['server_native_success_stops_chunk_cases'] += server.get('native_success_stops_chunk') is True
            group['server_private_truth_used_for_control_cases'] += server.get('private_joint_or_predicate_used_for_control') is True
            group['registered_prompt_mismatch_cases'] += item['registered_prompt_match'] is False
            if any(m.get('requested_action_count') != 5 or m.get('executed_action_count') != 5 for m in chunks) or controls['vla_chunks'] > 160 or item['registered_prompt_match'] is False or server.get('native_success_stops_chunk') is True or server.get('private_joint_or_predicate_used_for_control') is True:
                anomalies.append({'case': case['name'], 'controls': controls, 'server': server, 'prompt_match': item['registered_prompt_match']})
    for table in report['by_type_method']:
        typ = table['type_method'].split('/')[0]
        group = groups[typ]
        table['control_and_setup_accounting'] = dict(group)
        failure_counts = {k: v for k, v in table['root_cause_counts'].items()
                          if k not in ('newly_satisfied', 'already_satisfied_preserved', 'success_initial_truth_unknown')}
        table['largest_endpoint_or_execution_failure'] = max(failure_counts.items(), key=lambda kv: kv[1]) if failure_counts else None
    summary = {'scope': 'Exact4327 frontmost-with-original-fit-gates plus measured-contact-clearance-v8 same20 visited development drawer selection; saved labels and controls only, no physical replay',
               'job_id': 4327, 'final': args.final, 'complete': report['complete'], 'snapshot_time_utc': now,
               'manifest': {'path': str(MANIFEST), 'sha256': MANIFEST_SHA}, 'source': source,
               'producer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
               'sacct': states, 'original_status_inputs': original_refs,
               'summary_source': report['source'], 'registered_cases': 20,
               'recorded_cases': report['overall']['recorded'], 'by_type': report['by_type_method'],
               'infrastructure': report['infrastructure'],
               'control_anomalies': anomalies, 'first_labels_and_controls': records,
               'formal_report': {'path': str(out / 'statistic/report.json'), 'sha256': sha(out / 'statistic/report.json')},
               'original_explicit_inputs': report['original_explicit_inputs'],
               'private_truth_scope': plan['private_labels'],
               'setup_scope': 'All20 registered native drawer cases have no setup; setup grasp truth is not applicable, not implicitly true',
               'qualification_authorized': False, 'new_physical_trials': 0, 'new_training_rows': 0,
               'original_labels_preserved': True}
    (out / 'control_setup_and_endpoint_report.json').write_text(json.dumps(summary, indent=2) + '\n')
    table_summary = [{k: t[k] for k in ('type_method', 'planned', 'completed_case_records', 'physical_first_attempts',
                     'private_known', 'private_successes', 'private_success_wilson_95CI', 'confusion',
                     'runtime_verified_unmeasured', 'root_cause_counts', 'largest_endpoint_or_execution_failure',
                     'control_and_setup_accounting')} for t in summary['by_type']]
    print(json.dumps({'out': str(out), 'complete': summary['complete'], 'sacct': states,
                      'recorded': summary['recorded_cases'], 'by_type': table_summary,
                      'infrastructure': summary['infrastructure'], 'control_anomaly_count': len(anomalies),
                      'formal_report_sha256': summary['formal_report']['sha256'],
                      'supplement_sha256': sha(out / 'control_setup_and_endpoint_report.json')}))


if __name__ == '__main__':
    main()
