# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Retain each old handoff rejection's exact check and public pose."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for case in json.loads(args.registry.read_bytes())['rows']:
        summary = json.loads(Path(case['raw_summary']).read_bytes())
        choices = Path(summary['choices']['path'])
        execution = next(d['execution'] for line in choices.read_bytes().splitlines()
            for d in json.loads(line)['execution_details']
            if 'skill_stop_reason' in d.get('execution', {}))
        rows.append({'case': case['case'], 'sampling_seed': case['seed'],
            'summary': case['raw_summary'], 'choices': str(choices),
            'stop_reason': execution['skill_stop_reason'], 'handoff': execution['handoff'],
            'controls': len(execution['trace']), 'last_public_state': execution['trace'][-1]['after'],
            'last_public_check': execution['checks'][-1]})
    args.output.write_text(json.dumps({'rows': rows, 'physics_steps': 0,
        'scope': 'unchanged old 10477 records; not rescored or used for training'}, indent=2))
    print(json.dumps({'rows': len(rows), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
