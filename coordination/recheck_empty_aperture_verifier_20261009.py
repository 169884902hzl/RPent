"""Replay public verifier frames; private truth is only a comparison label."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from robots.libero import v5_grasp_public_tracking as tracking


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    closed = args.output / 'closed_ledgers'
    closed.mkdir()
    records, inputs, counts = [], [], Counter()
    for root in args.root:
        for manifest in sorted(root.glob('*/preparation/selection.json')):
            plan = json.loads(manifest.read_text())
            base_path = Path(plan['base_config']['path'])
            if ref(base_path) != plan['base_config']:
                raise ValueError('registered calibration source changed')
            base = json.loads(base_path.read_text())
            inputs.extend([ref(manifest), ref(base_path)])
            for ledger in sorted(manifest.parent.parent.glob('job*/part*/probe/episodes.jsonl')):
                raw = ledger.read_bytes()
                boundary = raw.rfind(b'\n') + 1
                snapshot = closed / (hashlib.sha256(str(ledger).encode()).hexdigest()[:20] + '.jsonl')
                snapshot.write_bytes(raw[:boundary])
                inputs.append({'source_ledger': str(ledger), 'closed_snapshot': ref(snapshot),
                               'trailing_unclosed_bytes': len(raw) - boundary})
                for line in raw[:boundary].splitlines():
                    row = json.loads(line)
                    if row.get('infrastructure_failure'):
                        continue
                    stage = row.get('first_attempt') or {}
                    receipt = stage.get('receipt') or {}
                    old = receipt.get('grasp_verified')
                    truth = stage.get('private_hold_truth_v2', {}).get('success')
                    verifier = stage.get('verification_measurements', {}).get('independent_grasp', {})
                    if not verifier:
                        choice_path = Path(row['output_dir']) / 'choices.jsonl'
                        inputs.append(ref(choice_path))
                        events = [json.loads(l) for l in choice_path.read_text().splitlines()]
                        verifier = next((e.get('verification_measurements', {}).get('independent_grasp', {})
                                         for e in events if e.get('selected') == stage.get('selected')), {})
                    frames = verifier.get('frames')
                    cfg = {**base, **plan['conditions'][row['case']['condition']].get('overrides', {})}
                    calibration = cfg.get('grasp_measurement_calibration', {}).get('opening_calibration')
                    new, evidence = old, None
                    if frames and len(frames) == 2 and calibration:
                        evaluated = tracking.evaluate_tracked_coupling(*frames, verifier['interval_s'],
                                                            opening_calibration=calibration)
                        new = evaluated['verified']
                        evidence = evaluated['empty_aperture_evidence']
                        counts['public_frame_replays'] += 1
                    else:
                        counts['no_complete_public_frame_pair_original_verdict_retained'] += 1
                    counts['recorded'] += 1
                    if isinstance(truth, bool):
                        counts['known_private_labels'] += 1
                        counts['old_agreement'] += int(old is truth)
                        counts['new_agreement'] += int(new is truth)
                        counts['new_fp'] += int(new is True and truth is False)
                        counts['new_fn'] += int(new is False and truth is True)
                        counts['new_null'] += int(new is None)
                    records.append({'case': row['case']['name'], 'category': row['case']['type'],
                        'method': row['case']['condition'], 'state_sha256': row['case']['state_sha256'],
                        'old_public': old, 'new_public': new,
                        'private_diagnostic_label': truth, 'empty_aperture_evidence': evidence,
                        'public_inputs_only': True, 'physical_execution_repeated': False,
                        'source_ledger': str(ledger), 'closed_source_snapshot': ref(snapshot), 'training_allowed': False})
    output = args.output / 'verifier_pairs.jsonl'
    output.write_text(''.join(json.dumps(row) + '\n' for row in records))
    report = {'counts': dict(counts), 'records': ref(output), 'inputs': inputs,
        'unique_registered_states': len({row['state_sha256'] for row in records}),
        'overlapping_pilots_and_selection_are_not_independent_confirmation': True,
        'source': [ref(Path(__file__)), ref(Path(tracking.__file__))],
        'new_physical_trials': 0, 'confirmation': False, 'training_allowed': False,
        'scope': 'offline development replay of saved public frames; unchanged or unknown values are preserved, not filled from truth'}
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'manifest': ref(path), 'counts': dict(counts)}))


if __name__ == '__main__':
    main()
