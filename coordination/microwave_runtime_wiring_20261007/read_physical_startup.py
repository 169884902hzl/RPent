"""Read only live server chunk accounting; do not send robot controls."""

import argparse
import json
from pathlib import Path
from rpent.utils.rpc.http_rpc import HttpRpcClient


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--job', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = HttpRpcClient(args.endpoint).call('diagnostic.skill501_chunks', timeout_s=15)
    result = {'job': args.job, 'readonly_method': 'diagnostic.skill501_chunks',
              'accounting': record, 'actual_physical_request_observed': record['requested_controls'] > 0,
              'actual_execution_observed': record['executed_controls'] > 0,
              'public_monitor_controls': 0, 'qualification': False}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
