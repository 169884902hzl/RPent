"""Compare saved same20 public geometry; no replay or verdict replacement."""

from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = Path(__file__).resolve().parent
FINAL = BASE / 'final_20261006T172531.587332Z'
OLD = ROOT / 'results/harness_v5/drawer559_monitor_CPU_20261006/final_20261006T164608.567363Z/statistic/report.json'
NEW = FINAL / 'statistic/report.json'


@lru_cache(maxsize=None)
def ref(path):
    path = Path(path)
    return {'path': str(path), 'exists': path.is_file(),
            **({'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} if path.is_file() else {})}


def load_rows(report):
    rows, refs = [], []
    for item in report['original_explicit_inputs']:
        if item['role'] == 'ledger' and item.get('exists'):
            path = Path(item['snapshot'])
            refs.append(ref(str(path)))
            for index, line in enumerate(path.read_text().splitlines(), 1):
                rows.append((json.loads(line), {'captured_ledger': ref(str(path)), 'line': index, 'original_ledger': item['path']}))
    return rows, refs


def category(first):
    metrology = (first.get('verification_measurements') or {}).get('articulation') or {}
    if not metrology:
        return 'metrology_not_run_' + str(first['receipt'].get('failure_reason', 'unrecorded'))
    missing = [phase + '_' + component for phase in ('before', 'after') for component in ('frame', 'moving')
               if not (metrology.get(phase) or {}).get(component)]
    return 'missing_' + '+'.join(missing) if missing else 'measured_' + str(metrology.get('reason', 'endpoint_result'))


def summary(row):
    first, case = row['first_attempt'], row['case']
    metro = (first.get('verification_measurements') or {}).get('articulation') or {}
    result = {'case': case['name'], 'public_verdict': first['receipt'].get('articulate_verified'),
              'truth_for_scoring_only': (first.get('private_after') or {}).get('satisfied'),
              'public_geometry_category': category(first), 'original_metrology': metro,
              'selected_public_entities': {}, 'RGBD_refs': [], 'direction_feature': {},
              'actual_front_axis_serialized': any('front_axis' in (metro.get(phase) or {}) for phase in ('before', 'after'))}
    outward = None
    for phase in ('before', 'after'):
        sample = metro.get(phase) or {}
        public = first.get('public_' + phase) or {}
        selected = first['receipt'].get('object')
        ids = {selected, sample.get('anchor_parent'), sample.get('anchor_part'), sample.get('current_part')}
        entities = [item for item in public.get('entities', []) if item['id'] in ids]
        result['selected_public_entities'][phase] = entities
        step = sample.get('source_step')
        if step is None:
            steps = [entity['source_step'] for entity in entities if entity.get('source_step') is not None]
            step = max(steps) if steps else None
        if step is not None:
            for camera in ('agentview', 'wrist'):
                result['RGBD_refs'].append({'phase': phase, 'camera': camera, 'source_step': step,
                    **ref(str(Path(row['output_dir']) / f'{camera}_world_high.npz/{step:02d}.npz'))})
        frame, moving = sample.get('frame'), sample.get('moving')
        if frame is None or moving is None:
            continue
        normal = np.asarray(frame['normal_xy'])
        delta = np.asarray(moving['centre'][:2]) - frame['centre'][:2]
        result['direction_feature'][phase + '_exact_abs_m'] = abs(float(delta @ normal))
        if phase == 'before' and public.get('robot', {}).get('eef_xyz') is not None:
            side = float((np.asarray(public['robot']['eef_xyz'][:2]) - frame['centre'][:2]) @ normal)
            result['direction_feature']['public_initial_eef_side_m'] = side
            if abs(side) > .01:
                outward = normal if side > 0 else -normal
                result['direction_feature']['inferred_public_outward_axis_xy'] = outward.tolist()
        if outward is not None:
            aligned = normal if float(normal @ outward) > 0 else -normal
            result['direction_feature'][phase + '_inferred_signed_m'] = float(delta @ aligned)
    return result


old_report, new_report = json.loads(OLD.read_text()), json.loads(NEW.read_text())
old_rows, old_refs = load_rows(old_report)
new_rows, new_refs = load_rows(new_report)
old_lookup = {(row['case']['type'], row['case']['state_sha256']): (row, locator) for row, locator in old_rows}
assert len(new_rows) == 20
counts, transitions, nulls, frame_support = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
items = []
for row, locator in new_rows:
    case = row['case']
    old_row, old_locator = old_lookup[(case['type'], case['state_sha256'])]
    assert old_row['case']['name'] == case['parent_case_name']
    newer, older = summary(row), summary(old_row)
    typ = case['type']
    counts[typ][str(newer['public_verdict'])] += 1
    transitions[typ][str(older['public_verdict']) + ' -> ' + str(newer['public_verdict'])] += 1
    if newer['public_verdict'] is None:
        nulls[typ][newer['public_geometry_category']] += 1
    for phase in ('before', 'after'):
        sample = newer['original_metrology'].get(phase) or {}
        frame_support[typ][phase + ':frame=' + str(bool(sample.get('frame'))) + ',moving=' + str(bool(sample.get('moving')))] += 1
    items.append({'case': case['name'], 'episode': case['episode'], 'type': typ, 'state_sha256': case['state_sha256'],
                  'new_locator': locator, 'old_locator': old_locator, 'source565': newer, 'source558_same_state': older,
                  'original_labels_preserved': True, 'control_comparison_scope': 'Both full160x5 runs; depth change can alter post-contact path and final physics, so success delta is not a fixed-label verifier comparison'})
records = FINAL / 'same20_public_frame_evidence.jsonl'
records.write_text(''.join(json.dumps(item) + '\n' for item in items))
report = {'scope': 'SOURCE565/job4287 same20 visited development public-frame comparison with original4254; no confirmation',
          'formal_new': ref(str(NEW)), 'formal_old': ref(str(OLD)), 'captured_new_ledgers': new_refs,
          'captured_old_ledgers': old_refs, 'registered_cases': 20, 'all20_original_states_matched': True,
          'new_public_verdict_counts': {key: dict(value) for key, value in counts.items()},
          'old_to_new_public_verdict_transitions': {key: dict(value) for key, value in transitions.items()},
          'new_null_categories': {key: dict(value) for key, value in nulls.items()},
          'new_public_component_support': {key: dict(value) for key, value in frame_support.items()},
          'new_measured_bounds_depth_rows': sum((item['source565']['original_metrology'].get('before') or {}).get('basis') == 'current_rgbd_measured_bounds_selected_drawer/5-dev' for item in items),
          'front_axis_serialized_rows': sum(item['source565']['actual_front_axis_serialized'] for item in items),
          'direction_scope': 'Original runtime front_axis absent. Signed diagnostic only orients recorded normal toward public initial EEF side; no qpos, symbol or label sets the axis',
          'new_public_false_positive_cases': [{'case': item['case'], 'episode': item['episode'],
                  'extension_cm': item['source565']['original_metrology'].get('measured_extension_cm'),
                  'geometry_category': item['source565']['public_geometry_category'],
                  'exact_distance': item['source565']['direction_feature']} for item in items
                  if item['source565']['public_verdict'] is True and item['source565']['truth_for_scoring_only'] is False],
          'raw_RGBD_ref_count': sum(len(item['source565']['RGBD_refs']) for item in items),
          'missing_raw_RGBD_refs': [entry for item in items for entry in item['source565']['RGBD_refs'] if not entry['exists']],
          'truth_scope': 'Saved satisfied label is for scoring strata only; no private coordinates exported or read into measurements',
          'control_comparison_limit': 'Changing public geometry may change the post-contact recovery path; old physical labels remain original and are never reused as labels for new physics',
          'records': ref(str(records)), 'producer': ref(__file__), 'private_qpos_used': False,
          'runtime_changed': False, 'new_model_calls': 0, 'new_physics': 0, 'qualification_authorized': False,
          'old_or_new_labels_changed': False}
path = FINAL / 'same20_public_frame_report.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': ref(str(path)), 'records': ref(str(records)),
                  **{key: report[key] for key in ('new_public_verdict_counts', 'old_to_new_public_verdict_transitions',
                     'new_null_categories', 'new_public_component_support', 'front_axis_serialized_rows',
                     'new_public_false_positive_cases', 'raw_RGBD_ref_count', 'missing_raw_RGBD_refs')}}))
