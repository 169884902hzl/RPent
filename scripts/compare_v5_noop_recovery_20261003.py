"""Replay observed measurement transitions; never claim a new policy rollout."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_state import Candidate, Entity


class LegacyRecovery(MeasuredRecovery):
    def observe(self, action, before, after):
        super().observe(action, before, after)
        if action.tool != 'reperceive':
            self.unchanged_reperceptions = 0


def snapshot(event, post=False):
    prefix = 'post_' if post else ''
    entities = [Entity(**{k: v for k, v in row.items() if k in Entity.__dataclass_fields__})
                for row in event[prefix + 'measurements']]
    context = event[prefix + 'request']['context']
    match = re.search(r'robot gripper_opening=([0-9.]+) held=(\S+)', context)
    if not match:
        raise ValueError('recorded robot measurement missing')
    return MeasuredRecovery.snapshot(entities, None if match[2] == 'none' else match[2], float(match[1]))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-report', required=True, type=Path)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if sha(args.source_report) != args.source_sha256:
        raise ValueError('registered complete development census changed')
    source = json.loads(args.source_report.read_text())
    groups, results = {}, []
    for episode in source['episodes']:
        path = Path(episode['trace'])
        if sha(path) != episode['trace_sha256']:
            raise ValueError('declared development trace changed')
        old, new, events, divergence = LegacyRecovery(), MeasuredRecovery(), Counter(), None
        for line in path.read_text().splitlines():
            row = json.loads(line)
            action = Candidate.from_text(row['receipt'].get('card_action') or row['selected'])
            before, after = snapshot(row), snapshot(row, True)
            if action.tool == 'reperceive' and not old.reperceive_cooldown and new.reperceive_cooldown:
                events['observed_reperceive_that_new_counter_would_suppress'] += 1
                if divergence is None:
                    divergence = {'decision': row['decision'], 'old': old.status(), 'new': new.status()}
            if action.tool == 'reperceive' and MeasuredRecovery.unchanged(before, after):
                events['observed_unchanged_reperceive'] += 1
            old.observe(action, before, after)
            new.observe(action, before, after)
        counts = groups.setdefault(episode['group'], Counter())
        counts['episodes'] += 1
        counts['episodes_with_first_counter_divergence'] += divergence is not None
        counts.update(events)
        results.append({'group': episode['group'], 'episode': episode['episode'],
                        'official_success': episode['official_success'], 'trace': str(path),
                        'trace_sha256': sha(path), 'events': dict(events),
                        'first_counter_divergence': divergence})
    report = {
        'scope': 'Offline replay of actual observed measured transitions. Suppression counts are counterfactual opportunities, not executed action reduction or new task success. Policy trajectories after the first divergence have not been evaluated.',
        'source_report': str(args.source_report), 'source_report_sha256': sha(args.source_report),
        'script_sha256': sha(__file__), 'groups': {k: dict(v) for k, v in groups.items()},
        'episodes': results, 'training_rows': 0, 'new_physical_executions': 0,
        'old_results_changed': False,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['groups']))


if __name__ == '__main__':
    main()
