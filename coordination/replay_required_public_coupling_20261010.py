"""Compare an explicit public co-motion gate on preserved selection frames."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling
from coordination.summarize_registered_grasp_v3r9_v2 import confusion


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('diagnoses', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    reports, rows = [], []
    for directory in args.diagnoses:
        path = directory / 'details.jsonl'
        data = path.read_bytes()
        records, mismatches = [], []
        for line in data.splitlines():
            saved = json.loads(line)
            pair = saved['pair_evidence']
            frames = pair.get('frames', [])
            new, status = saved['public'], 'no_paired_frame_evidence_unchanged'
            evidence = None
            if len(frames) == 2 and 'coupled_lift_evidence' in pair:
                calibration = (pair.get('empty_aperture_evidence') or {}).get('calibration')
                old = evaluate_tracked_coupling(*frames, pair['interval_s'],
                                               opening_calibration=calibration)
                if old['verified'] is not saved['public']:
                    mismatches.append(saved['case'])
                    status = 'old_verdict_not_reproduced_unchanged'
                else:
                    evidence = evaluate_tracked_coupling(*frames, pair['interval_s'],
                        opening_calibration=calibration, require_coupled_motion=True)
                    new, status = evidence['verified'], 'same_public_frames_rejudged'
            record = {**saved, 'public_original': saved['public'], 'public': new,
                      'registered_v3': saved['truth'], 'replay_status': status,
                      'new_coupling_evidence': evidence, 'diagnosis_source': pin(path),
                      'new_physics_execution': False, 'training_allowed': False}
            records.append(record)
        if mismatches:
            raise ValueError('cannot reproduce old public verdict: ' + str(mismatches))
        rows.extend(records)
        reports.append({'diagnosis': pin(path), 'n': len(records),
            'before': confusion([{**r, 'public': r['public_original']} for r in records], 'registered_v3'),
            'after': confusion(records, 'registered_v3'),
            'public_transitions': dict(Counter(f"{r['public_original']}->{r['public']}" for r in records)),
            'old_verdict_reproduction_mismatches': mismatches})
    (args.output / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    report = {'source': pin(Path(evaluate_tracked_coupling.__code__.co_filename)),
              'producer': pin(Path(__file__)), 'groups': reports,
              'qualification_allowed': False, 'new_physics_execution': False,
              'truth_rules_and_old_records_unchanged': True,
              'only_public_evidence_used_by_verifier': True}
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
