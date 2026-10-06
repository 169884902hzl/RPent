"""Extract public-only comparison details, distinguishing fresh frame pairs."""

from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np


BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
REPORT = OUT / 'report.json'
RECORDS = OUT / 'same20_geometry_comparison.jsonl'
SOURCE = BASE.parents[2] / 'source_v5_drawer565_20261006'
sys.path.insert(0, str(SOURCE))
from robots.libero.v5_state import Entity
spec = importlib.util.spec_from_file_location('frontmost_cpu_snapshot', BASE / 'v7_measured_drawer_faces_cpu.py')
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


items = list(map(json.loads, RECORDS.read_text().splitlines()))
counts, changed, new_nulls, unstable = Counter(), [], [], []
table_rows = []
for item in items:
    off, on = [item['pair_comparison'][mode] for mode in ('default_off', 'v7_on')]
    fresh = item['fresh_before_after_public_steps']
    counts['registered'] += 1
    counts['fresh_pairs'] += fresh
    counts['duplicate_step0_without_after'] += not fresh
    counts['fresh_pairs_fixed_frame_stable'] += fresh and off['frame_stability'].get('passes_original_frame_gates') is True
    counts['fresh_pairs_fixed_frame_unstable'] += fresh and off['frame_stability'].get('passes_original_frame_gates') is False
    for phase, capture in item['captures'].items():
        a, b = [capture['joined_and_original_view_disagreement_gates'][mode] for mode in ('default_off', 'v7_on')]
        counts['fixed_frame_off_on_captures_identical'] += capture['fixed_frame_identical_off_vs_v7']
        if a['evidence'].get('moving') != b['evidence'].get('moving'):
            changed.append({'case': item['case'], 'phase': phase, 'off_moving': a['evidence'].get('moving'),
                            'v7_moving': b['evidence'].get('moving')})
    if fresh and off['frame_stability'].get('passes_original_frame_gates') is False:
        unstable.append({'case': item['case'], 'frame_stability': off['frame_stability'],
                         'fixed_frames_identical_under_flag': all(capture['fixed_frame_identical_off_vs_v7'] for capture in item['captures'].values())})
    if off['original_v5_geometry_verdict_diagnostic'] is not None and on['original_v5_geometry_verdict_diagnostic'] is None:
        capture = item['captures']['after']
        cloud = capture['joined_and_original_view_disagreement_gates']['default_off']['clouds']['moving']
        front = np.asarray(item['public_axis_candidate_xy'])
        tangent = np.array([-front[1], front[0]])
        parent = item['public_initial_parent']
        corners = np.array([(x, y) for x in (parent['lower'][0], parent['upper'][0])
                            for y in (parent['lower'][1], parent['upper'][1])])
        width = float(np.ptp(corners @ tangent))
        new_nulls.append({'case': item['case'], 'missing_phase': 'after',
                         'prior_supported_moving_cloud': cloud, 'public_parent_width_m': width,
                         'visible_cloud_width_fraction': cloud['tangent_width_m'] / width,
                         'v7_required_width_m': .5 * width,
                         'width_shortfall_m': .5 * width - cloud['tangent_width_m'],
                         'wrist_already_had_no_moving_fit': capture['views']['wrist']['default_off']['evidence'].get('moving') is None,
                         'fixed_frame_stability': off['frame_stability']})
    table_rows.append({'case': item['case'], 'type': item['type'], 'fresh_after': fresh,
        'original_runtime_geometry_category': item['original_public_geometry_category'],
        'off_geometry_known': off['original_v5_geometry_verdict_diagnostic'] is not None,
        'v7_geometry_known': on['original_v5_geometry_verdict_diagnostic'] is not None,
        'off_reason': off.get('reason'), 'v7_reason': on.get('reason'),
        'off_signed_m': off.get('public_cardinal_signed_extension_m'),
        'v7_signed_m': on.get('public_cardinal_signed_extension_m'),
        'frame_drift_m': off['frame_stability'].get('normal_drift_m'),
        'frame_angle_deg': off['frame_stability'].get('normal_angle_deg'),
        'frame_stability_claimable_from_fresh_pair': fresh and off['frame_stability'].get('passes_original_frame_gates') is True})
table = OUT / 'same20_geometry_comparison.tsv'
with table.open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(table_rows[0]), delimiter='\t')
    writer.writeheader()
    writer.writerows(table_rows)
t8 = json.loads((OUT / 't8s18_geometry_comparison.json').read_text())
capture = t8['after_capture_comparison']['joined_and_original_view_disagreement_gates']
t8_planes = {}
for mode in ('default_off', 'v7_on'):
    evidence = capture[mode]['evidence']
    normal = np.asarray(evidence['frame']['normal_xy'])
    exact_abs = abs(float((np.asarray(evidence['moving']['centre'][:2]) - evidence['frame']['centre'][:2]) @ normal))
    t8_planes[mode] = {'signed_cardinal_extension_m': t8[mode + '_signed_extension_m'] if mode == 'default_off' else t8['v7_signed_extension_m'],
                       'exact_abs_original_normal_extension_m': exact_abs,
                       'moving_fit': evidence['moving'], 'moving_support': capture[mode]['clouds']['moving']}
prior_t8 = json.loads(Path(t8['prior_public_analysis']['path']).read_text())
parent, part = [Entity(**{key: prior_t8[label][key] for key in Entity.__dataclass_fields__ if key in prior_t8[label]})
                for label in ('public_initial_parent', 'public_initial_part')]
front = np.asarray(t8['public_axis_candidate_xy'])
worlds, before_refs = [], []
for camera in ('agentview', 'wrist'):
    old_path = Path(prior_t8['views'][camera]['public_RGBD']['path'])
    path = old_path.parent / '00.npz'
    before_refs.append({'camera': camera, 'phase': 'before', 'source_step': 0, **ref(path)})
    worlds.append(np.load(path)['array'].reshape(-1, 3))
before_joined = np.concatenate(worlds)
old_row = next(json.loads(line) for line in Path(prior_t8['captured_ledger']['path']).read_text().splitlines()
               if json.loads(line)['case']['name'] == t8['case'])
original_before = old_row['first_attempt']['verification_measurements']['articulation']['before']
t8_before_comparison = {}
for mode, flag in [('default_off', False), ('v7_on', True)]:
    evidence, _ = implementation.measured_drawer_faces(before_joined, parent, part, [*front, 0.],
                moving_part=part, measured_bounds_depth=False, frontmost_panel=flag)
    a, b = evidence['frame'], capture[mode]['evidence']['frame']
    normal = np.asarray(b['normal_xy'])
    drift = abs(float((np.asarray(b['centre'][:2]) - a['centre'][:2]) @ normal))
    angle = math.degrees(math.acos(float(np.clip(abs(normal @ a['normal_xy']), 0, 1))))
    t8_before_comparison[mode] = {'frame': evidence['frame'], 'moving': evidence['moving'],
        'fixed_frame_temporal_drift_m': drift, 'fixed_frame_temporal_angle_deg': angle,
        'fixed_frame_temporally_stable': drift <= .01 and angle <= 10,
        'matches_original_before_frame': evidence['frame'] == {key: original_before['frame'][key]
                          for key in ('centre', 'normal_xy', 'residual_p90_m', 'points')},
        'matches_original_before_moving': evidence['moving'] == {key: original_before['moving'][key]
                          for key in ('centre', 'normal_xy', 'residual_p90_m', 'points')}}
summary = {'scope': 'Public-only saved-frame v7 comparison details; duplicate captures are not frame stability evidence',
           'base_report': ref(REPORT), 'records': ref(RECORDS), 'producer': ref(__file__),
           'same20': dict(counts), 'new_null_cases': new_nulls,
           'moving_fit_changes': changed, 'preexisting_unstable_fixed_frame': unstable,
           't8_public_planes': t8_planes, 't8_fixed_frame_exactly_identical': t8['after_capture_comparison']['fixed_frame_identical_off_vs_v7'],
           't8_original_before_world_refs': before_refs, 't8_before_comparison': t8_before_comparison,
           'threshold_scope': 'The configured width fraction is reported without tuning it from these selected examples',
           'freshness_limit': 'Two original waypoint failures only expose a duplicated step0 capture. Their original endpoint remains unknown and their identical frame fits do not prove temporal stability',
           'axis_scope': 'Public-only cardinal axis reconstruction; no serialized old runtime axis is claimed',
           'private_qpos_or_truth_used': False, 'new_physics': 0, 'new_model_calls': 0,
           'shared_runtime_or_original_labels_changed': False, 'table': ref(table)}
path = OUT / 'public_geometry_summary.json'
path.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'summary': ref(path), 'table': ref(table), 'counts': dict(counts),
                  'new_null_cases': new_nulls, 't8_public_planes': t8_planes}))
