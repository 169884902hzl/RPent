"""Compare original-task geometry probes through their explicit episode ledgers."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_binding(private, entity, object_id):
    """Resolve private diagnostic references without changing the action."""
    names = [name for name, public in private.get('bindings', {}).items()
             if public == object_id]
    if len(names) == 1:
        return names[0], 'oracle_binding'
    if names or entity is None:
        return None, 'unresolved_binding'
    # A unique-category probe bypasses oracle.choose, so it has no predicate
    # bindings. Only a unique matching original object reference is usable.
    from robots.libero.v5_runtime import category
    names = [name for name in private.get('reference', {})
             if category(name) == entity['name']]
    if len(names) == 1:
        return names[0], 'unique_original_reference_category'
    return None, 'unresolved_reference_category'


def summarize(root, *, trajectories=False):
    ledger = root / 'episodes.jsonl'
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    records, counts = [], Counter()
    for row in rows:
        trace = Path(row['output_dir']) / 'choices.jsonl'
        events = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        if len(events) > 1 and not trajectories:
            raise ValueError('geometry first-grasp probe contains multiple decisions')
        if trajectories:
            counts['recorded_episodes'] += 1
            counts['official_success'] += row['result'].get('official_success') is True
            counts['actual_first_grasps'] += any(e.get('receipt', {}).get('tool') == 'grasp' for e in events)
            for event in events:
                receipt = event.get('receipt', {})
                measurements = [*event.get('measurements', []), *event.get('post_measurements', [])]
                counts['recorded_decisions'] += 1
                counts['actual_grasp_attempts'] += receipt.get('tool') in ('grasp', 'regrasp_restage')
                counts['grasp_verified'] += receipt.get('grasp_verified') is True
                counts['execution_error'] += receipt.get('verification') == 'execution_error'
                counts['shape_prior_measurements'] += sum(e.get('src') == 'perception_shape_prior' for e in measurements)
                counts['shape_prior_action_targets'] += any(
                    m.get('id') == receipt.get('object') and m.get('src') == 'perception_shape_prior'
                    for m in event.get('measurements', []))
                counts['cached_target_actions'] += receipt.get('object_geometry_source') == 'last_perception_measurement'
                counts['cached_held_actions'] += receipt.get('held_geometry_source') == 'last_visual_grasp_measurement_and_gripper'
                probed = receipt.get('occlusion_probe') == 'current_wrist_rgbd_before_first_place'
                missing = probed and receipt.get('occlusion_probe_missing') is True
                counts['wrist_occlusion_probes'] += probed
                counts['wrist_occlusion_missing'] += missing
                counts['wrist_occlusion_missing_place_verified'] += missing and receipt.get('place_verified') is True
                counts['wrist_occlusion_missing_execution_errors'] += missing and receipt.get('verification') == 'execution_error'
                counts['cached_measurement_records'] += sum('cached' in str(e.get('src')) for e in measurements)
                counts['missing_visible_execution_errors'] += (
                    receipt.get('verification') == 'execution_error'
                    and 'visible measurement' in receipt.get('error', ''))
                counts['recoverable_waypoint_failures'] += receipt.get('failure_reason') == 'waypoint_not_reached'
            records.append({'episode': row['episode'], 'trace': str(trace),
                            'trace_sha256': digest(trace) if trace.exists() else None,
                            'official_success': row['result'].get('official_success'),
                            'termination_category': row['result'].get('termination_category'),
                            'diagnostic_events': events})
            continue
        event = events[0] if events else {}
        receipt = event.get('receipt', {})
        measurements = event.get('measurements', [])
        post = event.get('post_measurements', [])
        object_id = receipt.get('object')
        entity = next((e for e in measurements if e['id'] == object_id), None)
        private = event.get('localization_diagnostic', {})
        wrist = next((e for e in reversed(event.get('motion_evidence', []))
                      if e.get('name') == 'shape_probe_wrist'), None)
        decision_entity = entity
        if wrist is not None:
            entity = wrist['measurement']
            private = {**private, 'reference': wrist['reference']}
        name, binding_source = reference_binding(private, entity, object_id)
        reference = private.get('reference', {}).get(name)
        reference_after = private.get('reference_after', {}).get(name)
        record = {'episode': row['episode'], 'trace': str(trace),
                  'trace_sha256': digest(trace) if trace.exists() else None,
                  'receipt': receipt, 'entity': entity, 'binding': name,
                  'binding_source': binding_source,
                  'official_success': row['result'].get('official_success'),
                  'measurement_sources': dict(Counter(e.get('src') for e in [*measurements, *post]))}
        if wrist is not None:
            record['decision_entity'] = decision_entity
            record['measurement_phase'] = 'actual_wrist_before_contact'
        if entity:
            record['estimated_height_m'] = entity['upper'][2] - entity['lower'][2]
        if entity and entity.get('visible') and reference and reference.get('reference') == 'body_origin':
            record['body_origin_proxy_error_m'] = math.dist(entity['xyz'], reference['xyz'])
            record['body_origin_proxy_z_error_m'] = entity['xyz'][2] - reference['xyz'][2]
        if reference and reference_after:
            record['private_body_z_rise_m'] = reference_after['xyz'][2] - reference['xyz'][2]
        counts['recorded_episodes'] += 1
        counts['actual_first_grasps'] += receipt.get('tool') == 'grasp'
        counts['grasp_verified'] += receipt.get('grasp_verified') is True
        counts['execution_error'] += receipt.get('verification') == 'execution_error'
        counts['shape_prior_target'] += bool(entity and entity.get('src') == 'perception_shape_prior')
        counts['cached_target_actions'] += receipt.get('object_geometry_source') == 'last_perception_measurement'
        counts['cached_held_actions'] += receipt.get('held_geometry_source') == 'last_visual_grasp_measurement_and_gripper'
        counts['cached_measurement_records'] += sum('cached' in str(e.get('src')) for e in [*measurements, *post])
        records.append(record)
    metrics = {}
    for key in ('body_origin_proxy_error_m', 'body_origin_proxy_z_error_m', 'estimated_height_m',
                'private_body_z_rise_m'):
        values = [r[key] for r in records if key in r]
        metrics[key] = {'count': len(values), 'median': statistics.median(values) if values else None}
    return {'ledger': str(ledger), 'ledger_sha256': digest(ledger),
            'counts': dict(counts), 'metrics': metrics, 'records': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trajectories', action='store_true')
    args = parser.parse_args()
    before, after = (summarize(path, trajectories=args.trajectories) for path in (args.before, args.after))
    key = lambda r: tuple(r['episode'][name] for name in ('suite', 'task', 'seed'))
    old, new = ({key(r): r for r in group['records']} for group in (before, after))
    if old.keys() != new.keys():
        raise ValueError('before/after original task identities differ; probe incomplete')
    report = {'scope': ('Original complete-trajectory geometry comparison' if args.trajectories
                        else 'Original first-grasp geometry probe')
                       + '; private body origin is not a geometric-centre truth.',
              'before': before, 'after': after,
              'pairs': [{'identity': identity, 'before': old[identity], 'after': new[identity]} for identity in old],
              'cache_action_coverage': after['counts'].get('cached_target_actions', 0),
              'cache_action_effect_verified': False,
              'cache_action_attempt_observed': after['counts'].get('cached_target_actions', 0) > 0,
              'shape_measurement_observed': after['counts'].get('shape_prior_measurements', 0) > 0 or after['counts'].get('shape_prior_target', 0) > 0,
              'shape_action_target_observed': after['counts'].get('shape_prior_action_targets', 0) > 0 or after['counts'].get('shape_prior_target', 0) > 0,
              'held_cache_action_observed': after['counts'].get('cached_held_actions', 0) > 0,
              'real_wrist_occlusion_observed': after['counts'].get('wrist_occlusion_missing', 0) > 0,
              'new_training_rows': 0, 'script_sha256': digest(Path(__file__))}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({a: {'counts': report[a]['counts'], 'metrics': report[a]['metrics']}
                      for a in ('before', 'after')}))


if __name__ == '__main__':
    main()
