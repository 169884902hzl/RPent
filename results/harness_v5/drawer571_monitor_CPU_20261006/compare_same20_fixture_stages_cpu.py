"""Pair exact original state/type records for drawer4319 versus drawer4327."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def one_run(row):
    scores = row['private_stage_scores']
    actual = scores['after_actual_chunk']
    first_true = next((s['chunk'] + 1 for s in actual if s['label'] and s['label']['satisfied'] is True), None)
    contact_losses = []
    for previous, current in zip(actual, actual[1:]):
        if previous['label'] and current['label'] and previous['label']['satisfied'] is True and current['label']['satisfied'] is False:
            contact_losses.append({'first_false_completed_chunk': current['chunk'] + 1,
                                  'previous': previous['label'], 'current': current['label']})
    phases = {phase: [sample['label'] for sample in values] for phase, values in scores.items()
              if phase != 'after_actual_chunk'}
    return {'case': row['case'], 'chunks': row['actual_vla_chunks'], 'controls': row['actual_executed_controls'],
            'all_chunks_complete5': row['every_chunk_complete5'],
            'first_saved_contact_endpoint_true_completed_chunk': first_true,
            'saved_contact_true_to_false_transitions': contact_losses,
            'public_stop': row['public_contact_stop'], 'private_stop': row['private_at_stop'],
            'private_last_actual_contact': row['private_after_contact'],
            'stop_already_strict_endpoint_false': row['stop_already_strict_endpoint_false'],
            'recovery_first_endpoint_loss_phase': row['recovery_first_endpoint_loss_phase'],
            'private_recovery_stages': phases, 'private_final': row['private_final'],
            'public_final': row['public_final'], 'public_final_signed_extension_m': row['public_final_signed_extension_m'],
            'public_final_null_reason': row['public_final_null_reason'],
            'clearance_reason': row['fixture_contact_clearance'].get('reason'),
            'clearance_view_restored': row['fixture_contact_clearance'].get('view_restored'),
            'original_ledger': row['locator'], 'original_labels_preserved': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before-dir', type=Path, required=True)
    parser.add_argument('--after-dir', type=Path, required=True)
    args = parser.parse_args()
    before_path = args.before_dir / 'fixture_stage_scoring_evidence.jsonl'
    after_path = args.after_dir / 'fixture_stage_scoring_evidence.jsonl'
    before = [json.loads(line) for line in before_path.read_text().splitlines()]
    after = [json.loads(line) for line in after_path.read_text().splitlines()]
    lookup = {(row['type'], row['state_sha256']): row for row in before}
    assert len(lookup) == len(before) == len(after) == 20
    assert set(lookup) == {(row['type'], row['state_sha256']) for row in after}
    groups, rows = defaultdict(Counter), []
    for row in after:
        prior = lookup[(row['type'], row['state_sha256'])]
        assert prior['episode'] == row['episode']
        old, new = one_run(prior), one_run(row)
        private_changed = old['private_final']['satisfied'] != new['private_final']['satisfied']
        item = {'episode': row['episode'], 'type': row['type'], 'state_sha256': row['state_sha256'],
                'before_4319': old, 'after_4327': new,
                'private_endpoint_changed': private_changed,
                'public_verdict_changed': old['public_final'] != new['public_final'],
                'extra_contact_chunks': new['chunks'] - old['chunks'],
                'extra_contact_controls': new['controls'] - old['controls']}
        rows.append(item)
        group = groups[row['type']]
        group['paired_cases'] += 1
        group['unchanged_final_private'] += not private_changed
        group['final_private_gain'] += old['private_final']['satisfied'] is False and new['private_final']['satisfied'] is True
        group['final_private_loss'] += old['private_final']['satisfied'] is True and new['private_final']['satisfied'] is False
        group['before_chunks'] += old['chunks']; group['after_chunks'] += new['chunks']
        group['before_controls'] += old['controls']; group['after_controls'] += new['controls']
        group['before_public_stops'] += old['public_stop']; group['after_public_stops'] += new['public_stop']
        group['before_stop_already_false'] += old['stop_already_strict_endpoint_false']
        group['after_stop_already_false'] += new['stop_already_strict_endpoint_false']
        group['before_saved_recovery_loss'] += old['recovery_first_endpoint_loss_phase'] is not None
        group['after_saved_recovery_loss'] += new['recovery_first_endpoint_loss_phase'] is not None
    records = args.after_dir / 'paired4319_4327_fixture_stages.jsonl'
    records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    table = args.after_dir / 'paired4319_4327_fixture_stages.tsv'
    with table.open('w') as handle:
        writer = csv.DictWriter(handle, delimiter='\t', fieldnames=['type', 'task', 'seed', 'before_chunks',
            'after_chunks', 'before_private', 'after_private', 'before_public', 'after_public',
            'before_stop_false', 'after_stop_false', 'before_recovery_loss', 'after_recovery_loss'])
        writer.writeheader()
        for item in rows:
            data = {'type': item['type'], 'task': item['episode']['task'], 'seed': item['episode']['seed']}
            for prefix, run in [('before', item['before_4319']), ('after', item['after_4327'])]:
                data.update({prefix+'_chunks': run['chunks'], prefix+'_private': run['private_final']['satisfied'],
                             prefix+'_public': run['public_final'], prefix+'_stop_false': run['stop_already_strict_endpoint_false'],
                             prefix+'_recovery_loss': run['recovery_first_endpoint_loss_phase']})
            writer.writerow(data)
    report = {'scope': 'Original same20 development state/type pairs; SOURCE569 v8 clearance versus SOURCE571 frontmost+v8 clearance',
              'before_records': ref(before_path), 'after_records': ref(after_path), 'producer': ref(__file__),
              'before_formal': ref(args.before_dir / 'statistic/report.json'),
              'after_formal': ref(args.after_dir / 'statistic/report.json'),
              'same_state_pairs': 20, 'by_type': {key: dict(value) for key, value in groups.items()},
              'changed_final_private_cases': [{'episode': item['episode'], 'type': item['type'],
                  'before': item['before_4319']['private_final'], 'after': item['after_4327']['private_final']}
                  for item in rows if item['private_endpoint_changed']],
              'changed_public_verdict_cases': [{'episode': item['episode'], 'type': item['type'],
                  'before': item['before_4319']['public_final'], 'after': item['after_4327']['public_final']}
                  for item in rows if item['public_verdict_changed']],
              'net_final_private_success_gain': sum(v['final_private_gain'] - v['final_private_loss'] for v in groups.values()),
              'records': ref(records), 'table': ref(table), 'new_model_calls': 0, 'new_physics': 0,
              'private_used_for_control': False, 'original_labels_preserved': True, 'qualification_authorized': False,
              'comparison_limit': 'Changed public measurements change contact stopping and actual physics. Same-state development selection supports diagnosis, not independent qualification or a causal performance guarantee'}
    path = args.after_dir / 'paired4319_4327_fixture_stages_report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': ref(path), 'records': ref(records), 'table': ref(table),
                      'by_type': report['by_type'], 'net_final_private_success_gain': report['net_final_private_success_gain']}))


if __name__ == '__main__':
    main()
