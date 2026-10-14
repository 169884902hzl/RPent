"""Measure startup of faulted registered states without executing any skill."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--faults', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    faults = json.loads(args.faults.read_text())
    cases = {case['name']: case for case in plan['cases']}
    sys.path[:0] = [plan['adapter_path'], plan['source_path']]
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for fault in faults:
        case = cases[fault['case']]
        raw = json.loads(Path(fault['input']).read_text().splitlines()[fault['line'] - 1])
        if (not raw.get('infrastructure_failure') or raw.get('first_attempt')
                or raw['case'] != case or raw.get('error_stage') != 'startup'):
            raise ValueError('only states without a first physical attempt may be probed')
        os.environ['V5_PERTURB_REGISTERED_STATE'] = json.dumps(case['registered_layout_state'])
        episode = case['episode']
        output = args.output / case['name']
        output.mkdir()
        endpoint_port = pick_free_port()
        command = [sys.executable, '-m', 'scripts.probe_v5_perturb_skill_20261009', '--serve',
                   '--suite', episode['suite'], '--task', str(episode['task']),
                   '--seed', str(episode['seed']), '--max-episode-steps', '10000',
                   '--port', str(endpoint_port)]
        daemon = ProcessDaemon(name='confirmation_env_reset_diagnostic', cmd=command,
                               log_path=str(output / 'oracle_env.log'))
        result = {'case': case['name'], 'state_sha256': case['state_sha256'],
                  'fault': fault, 'controller_skill_executed': False,
                  'model_outputs_read': False, 'registered_state_changed': False}
        started = time.monotonic()
        try:
            daemon.start()
            rpc = HttpRpcClient(f'http://127.0.0.1:{endpoint_port}')
            wait_for_ready(rpc, daemon=daemon, timeout_s=300)
            result['rpc_ready_s'] = time.monotonic() - started
            reset_start = time.monotonic()
            rpc.call('env.reset', timeout_s=600)
            result['reset_s'] = time.monotonic() - reset_start
            result['registered_restore'] = rpc.call('diagnostic.perturb_registered_reset', timeout_s=30)
            result['status'] = 'reset_pass'
        except Exception as error:
            result.update(status='reset_error', error=repr(error))
        finally:
            daemon.stop()
        result['wall_s'] = time.monotonic() - started
        records.append(result)
        (args.output / 'records.json').write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    (args.output / 'manifest.json').write_text(json.dumps({
        'plan': pin(args.plan), 'faults': pin(args.faults), 'producer': pin(Path(__file__)),
        'records': pin(args.output / 'records.json'), 'source_identity': pin(
            Path(plan['source_path']) / 'source_identity_v3r9.json'),
        'training_allowed': False, 'qualification_allowed': False,
        'purpose': 'startup timing only; no confirmation physical outcome'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
