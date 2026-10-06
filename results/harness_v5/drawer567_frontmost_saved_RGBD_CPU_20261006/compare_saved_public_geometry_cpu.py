"""Compare the v7 moving-face flag on explicit original public RGB-D files."""

from collections import Counter
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
SOURCE = ROOT / 'source_v5_drawer565_20261006'
SAME20 = ROOT / 'results/harness_v5/drawer565_monitor_CPU_20261006/final_20261006T172531.587332Z/same20_public_frame_evidence.jsonl'
T8 = ROOT / 'results/harness_v5/drawer559_monitor_CPU_20261006/final_20261006T164608.567363Z/t8s18_public_plane_analysis.json'
sys.path.insert(0, str(SOURCE))
from robots.libero.v5_fixture_parts import measured_drawer_faces as frozen_v5_faces
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import measured_fixture_endpoint, vertical_face

spec = importlib.util.spec_from_file_location('frontmost_cpu_snapshot', BASE / 'v7_measured_drawer_faces_cpu.py')
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)


@lru_cache(maxsize=None)
def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def entity(raw):
    return Entity(**{key: raw[key] for key in Entity.__dataclass_fields__ if key in raw})


def fit_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    return (a['points'] == b['points'] and np.allclose(a['centre'], b['centre'], atol=1e-12, rtol=0)
            and np.allclose(a['normal_xy'], b['normal_xy'], atol=1e-12, rtol=0)
            and abs(a['residual_p90_m'] - b['residual_p90_m']) <= 1e-12)


def cloud_summary(points, front):
    if not len(points):
        return {'points': 0}
    tangent = np.array([-front[1], front[0]])
    return {'points': len(points), 'lower': np.min(points, axis=0).tolist(),
            'upper': np.max(points, axis=0).tolist(),
            'height_span_m': float(np.ptp(points[:, 2])),
            'tangent_width_m': float(np.ptp(points[:, :2] @ tangent))}


def axis_from_public(before, saved_before, part):
    if saved_before.get('outward_axis_xy') is not None:
        return np.asarray(saved_before['outward_axis_xy']), 'original_serialized_public_outward_axis'
    frame = saved_before.get('frame')
    eef = np.asarray(before['robot']['eef_xyz'])
    if frame is not None:
        normal = np.asarray(frame['normal_xy'])
        side = float((eef[:2] - frame['centre'][:2]) @ normal)
        if abs(side) <= .01:
            raise ValueError('Public EEF side cannot orient the original frame')
        outward = normal if side > 0 else -normal
        axis = np.zeros(2)
        index = np.argmax(np.abs(outward))
        axis[index] = np.sign(outward[index])
        return axis, 'public_before_frame_normal_oriented_to_public_initial_EEF_side_then_cardinalized'
    spans = np.asarray(part.upper[:2]) - part.lower[:2]
    index = int(np.argmin(spans))
    side = eef[index] - part.xyz[index]
    if abs(side) <= .01 or spans[1 - index] <= 2 * spans[index]:
        raise ValueError('No measured public thin-part axis with a clear EEF side')
    axis = np.zeros(2)
    axis[index] = np.sign(side)
    return axis, 'public_selected_part_thin_AABB_axis_and_public_initial_EEF_side_no_original_metrology'


def capture(refs, parent, part, current, front, depth_flag, step, saved=None):
    worlds = []
    views = {}
    for camera in ('agentview', 'wrist'):
        entry = next(item for item in refs if item['camera'] == camera)
        path = Path(entry['path'])
        if ref(str(path))['sha256'] != entry['sha256']:
            raise ValueError('Original explicit public RGB-D file changed: ' + str(path))
        world = np.load(path)['array']
        worlds.append(world.reshape(-1, 3))
        modes = {}
        for mode, flag in [('default_off', False), ('v7_on', True)]:
            evidence, clouds = implementation.measured_drawer_faces(world, parent, part, [*front, 0.],
                moving_part=current, measured_bounds_depth=depth_flag, frontmost_panel=flag)
            modes[mode] = {'evidence': evidence,
                           'clouds': {key: cloud_summary(value, front) for key, value in clouds.items()}}
        original = (saved or {}).get('views', {}).get(camera)
        views[camera] = {'public_RGBD': ref(str(path)), **modes,
                         'original_default_off_match': {key: fit_equal(original.get(key), modes['default_off']['evidence'].get(key))
                           for key in ('frame', 'moving') if key in original} if original is not None else None}
    joined = np.concatenate(worlds)
    joined_result = {}
    for mode, flag in [('default_off', False), ('v7_on', True)]:
        evidence, clouds = implementation.measured_drawer_faces(joined, parent, part, [*front, 0.],
            moving_part=current, measured_bounds_depth=depth_flag, frontmost_panel=flag)
        disagreements = {}
        for component in ('frame', 'moving'):
            a = views['agentview'][mode]['evidence'].get(component)
            b = views['wrist'][mode]['evidence'].get(component)
            if a is not None and b is not None:
                normal = np.asarray(a['normal_xy'])
                distance = abs(float((np.asarray(a['centre'][:2]) - b['centre'][:2]) @ normal))
                cosine = abs(float(normal @ b['normal_xy']))
                if distance > .015 or cosine < .95:
                    evidence[component] = None
                    disagreements[component] = {'normal_distance_m': distance, 'normal_cosine': cosine}
        if disagreements:
            evidence.update(reason='drawer_views_disagree', view_disagreements=disagreements)
        evidence.update(source_step=step, source='perception')
        joined_result[mode] = {'evidence': evidence,
                               'clouds': {key: cloud_summary(value, front) for key, value in clouds.items()}}
    frozen, _ = frozen_v5_faces(joined, parent, part, [*front, 0.], moving_part=current,
                                measured_bounds_depth=depth_flag)
    off = joined_result['default_off']['evidence']
    return {'views': views, 'joined_and_original_view_disagreement_gates': joined_result,
            'v7_flag_default_off_matches_frozen_v5_raw_joined': {key: fit_equal(off.get(key), frozen.get(key))
              if not off.get('view_disagreements', {}).get(key) else None for key in ('frame', 'moving')},
            'original_fused_default_off_match': {key: fit_equal((saved or {}).get(key), off.get(key))
              for key in ('frame', 'moving')} if saved is not None else None,
            'fixed_frame_identical_off_vs_v7': fit_equal(off.get('frame'), joined_result['v7_on']['evidence'].get('frame'))}


def frame_stability(before, after):
    a, b = before.get('frame'), after.get('frame')
    if a is None or b is None:
        return {'available': False}
    normal = np.asarray(b['normal_xy'])
    angle = math.degrees(math.acos(float(np.clip(abs(normal @ a['normal_xy']), 0, 1))))
    drift = abs(float((np.asarray(b['centre'][:2]) - a['centre'][:2]) @ normal))
    return {'available': True, 'normal_angle_deg': angle, 'normal_drift_m': drift,
            'passes_original_frame_gates': angle <= 10 and drift <= .01}


def pair_result(before, after, mode, front):
    verdict, evidence = measured_fixture_endpoint(before, after, mode, drawer=True)
    result = {'original_v5_geometry_verdict_diagnostic': verdict, 'reason': evidence.get('reason'),
              'original_v5_abs_extension_cm': evidence.get('measured_extension_cm'),
              'frame_stability': frame_stability(before, after)}
    if after.get('frame') and after.get('moving'):
        result['public_cardinal_signed_extension_m'] = float((np.asarray(after['moving']['centre'][:2])
                 - after['frame']['centre'][:2]) @ front)
    return result


OUT.mkdir(exist_ok=False)
items = []
input20 = list(map(json.loads, SAME20.read_text().splitlines()))
assert len(input20) == 20
explicit_refs = [entry for item in input20 for entry in item['source565']['RGBD_refs']]
assert len(explicit_refs) == 80
for index, item in enumerate(input20, 1):
    locator = item['new_locator']
    captured = Path(locator['captured_ledger']['path'])
    if ref(str(captured))['sha256'] != locator['captured_ledger']['sha256']:
        raise ValueError('Captured original ledger changed')
    row = json.loads(captured.read_text().splitlines()[locator['line'] - 1])
    first = row['first_attempt']
    # Only public fields are accessed. Neither qpos, success labels, joint
    # traces nor simulator snapshots enter this comparison.
    before, after = first['public_before'], first['public_after']
    before_entities = {entity['id']: entity for entity in before['entities']}
    after_entities = {entity['id']: entity for entity in after['entities']}
    part = entity(before_entities[first['receipt']['object']])
    parent = entity(before_entities[part.part_of])
    current = entity(after_entities[part.id])
    metro = item['source565']['original_metrology']
    front, axis_method = axis_from_public(before, metro.get('before') or {}, part)
    record = {'case': item['case'], 'episode': item['episode'], 'type': item['type'],
              'state_sha256': item['state_sha256'], 'original_public_geometry_category': item['source565']['public_geometry_category'],
              'public_axis_candidate_xy': front.tolist(), 'public_axis_reconstruction_method': axis_method,
              'actual_runtime_axis_not_serialized': True, 'original_locator': locator,
              'public_initial_parent': before_entities[parent.id], 'public_initial_part': before_entities[part.id],
              'public_current_part': after_entities[part.id], 'captures': {}}
    for phase, part_current in [('before', part), ('after', current)]:
        refs = [entry for entry in item['source565']['RGBD_refs'] if entry['phase'] == phase]
        step = refs[0]['source_step']
        saved = metro.get(phase)
        record['captures'][phase] = capture(refs, parent, part, part_current, front, True, step, saved)
    record['fresh_before_after_public_steps'] = (item['source565']['RGBD_refs'][0]['source_step']
         != next(entry['source_step'] for entry in item['source565']['RGBD_refs'] if entry['phase'] == 'after'))
    record['original_runtime_metrology_ran'] = bool(metro)
    record['pair_comparison'] = {mode: pair_result(record['captures']['before']['joined_and_original_view_disagreement_gates'][mode]['evidence'],
        record['captures']['after']['joined_and_original_view_disagreement_gates'][mode]['evidence'], row['case']['mode'], front)
        for mode in ('default_off', 'v7_on')}
    record['old_labels_preserved'] = True
    items.append(record)
    print(json.dumps({'progress': index, 'case': item['case'], 'comparison': record['pair_comparison']}), flush=True)

t8 = json.loads(T8.read_text())
parent, part, current = [entity(t8[key]) for key in ('public_initial_parent', 'public_initial_part', 'public_current_part')]
front = np.asarray(t8['inferred_public_axis_xyz'][:2])
after_refs = [{'camera': camera, **view['public_RGBD']} for camera, view in t8['views'].items()]
t8_capture = capture(after_refs, parent, part, current, front, False, 1,
    {'frame': t8['saved_after_frame'], 'moving': t8['saved_after_moving'],
     'views': {camera: {'moving': view['saved_per_camera_moving']} for camera, view in t8['views'].items()}})
off = t8_capture['joined_and_original_view_disagreement_gates']['default_off']['evidence']
on = t8_capture['joined_and_original_view_disagreement_gates']['v7_on']['evidence']
t8_result = {'case': t8['case'], 'prior_public_analysis': ref(str(T8)), 'public_axis_candidate_xy': front.tolist(),
             'axis_scope': t8['front_axis_scope'], 'after_capture_comparison': t8_capture,
             'default_off_signed_extension_m': float((np.asarray(off['moving']['centre'][:2]) - off['frame']['centre'][:2]) @ front) if off['moving'] and off['frame'] else None,
             'v7_signed_extension_m': float((np.asarray(on['moving']['centre'][:2]) - on['frame']['centre'][:2]) @ front) if on['moving'] and on['frame'] else None}
counts = {mode: Counter() for mode in ('default_off', 'v7_on')}
new_nulls, reproduction_failures, frame_changes = [], [], []
for item in items:
    for mode in counts:
        result = item['pair_comparison'][mode]
        counts[mode]['registered_cases'] += 1
        counts[mode]['distinct_public_capture_pairs'] += item['fresh_before_after_public_steps']
        counts[mode]['counterfactual_geometry_known_pairs'] += result['original_v5_geometry_verdict_diagnostic'] is not None
        counts[mode]['counterfactual_geometry_null_pairs'] += result['original_v5_geometry_verdict_diagnostic'] is None
        counts[mode]['original_metrology_ran_pairs'] += item['original_runtime_metrology_ran']
        counts[mode]['frame_stable_pairs'] += result['frame_stability'].get('passes_original_frame_gates') is True
        counts[mode]['frame_unstable_pairs'] += result['frame_stability'].get('passes_original_frame_gates') is False
        for phase, capture_result in item['captures'].items():
            evidence = capture_result['joined_and_original_view_disagreement_gates'][mode]['evidence']
            counts[mode][phase + '_frame_available'] += evidence.get('frame') is not None
            counts[mode][phase + '_moving_available'] += evidence.get('moving') is not None
    old, new = item['pair_comparison']['default_off'], item['pair_comparison']['v7_on']
    if old['original_v5_geometry_verdict_diagnostic'] is not None and new['original_v5_geometry_verdict_diagnostic'] is None:
        new_nulls.append({'case': item['case'], 'before': old, 'after_v7': new})
    for phase, capture_result in item['captures'].items():
        if not capture_result['fixed_frame_identical_off_vs_v7']:
            frame_changes.append({'case': item['case'], 'phase': phase})
        match = capture_result['original_fused_default_off_match']
        if match is not None and not all(match.values()):
            reproduction_failures.append({'case': item['case'], 'phase': phase, 'match': match})
        for camera, view in capture_result['views'].items():
            match = view['original_default_off_match']
            if match is not None and not all(match.values()):
                reproduction_failures.append({'case': item['case'], 'phase': phase, 'camera': camera, 'match': match})
records = OUT / 'same20_geometry_comparison.jsonl'
records.write_text(''.join(json.dumps(item) + '\n' for item in items))
t8_path = OUT / 't8s18_geometry_comparison.json'
t8_path.write_text(json.dumps(t8_result, indent=2) + '\n')
input_path = OUT / 'explicit_public_world_refs.json'
input_path.write_text(json.dumps({'same20_refs': explicit_refs, 't8_after_refs': after_refs}, indent=2) + '\n')
report = {'scope': 'Original t8/s18 plus exact4287 same20 saved public RGB-D flag-off/flag-on CPU geometry comparison only',
          'same20_public_record_source': ref(str(SAME20)), 't8_public_analysis_source': ref(str(T8)),
          'implementation_snapshot': json.loads((BASE / 'implementation_snapshot.json').read_text()),
          'dependencies': [ref(SOURCE / 'robots/libero/v5_state.py'), ref(SOURCE / 'robots/libero/v5_verification.py')],
          'registered_cases': 20, 'explicit_same20_world_refs': 80,
          'distinct_same20_world_files': len({entry['path'] for entry in explicit_refs}),
          'same20': {mode: dict(count) for mode, count in counts.items()},
          'new_geometry_nulls_under_v7': new_nulls, 'original_default_off_reproduction_failures': reproduction_failures,
          'fixed_frame_changed_by_v7': frame_changes, 't8_result': {key: t8_result[key] for key in
               ('case', 'default_off_signed_extension_m', 'v7_signed_extension_m')},
          'missing_after_policy': 'Two original waypoint failures only saved step0 twice. Their lack of a fresh after measurement remains unknown; recomputing the same capture is not a new endpoint',
          'direction_scope': 'The old runtime axis was not serialized. Public-before measured frame normal and EEF side supply a cardinal CPU candidate, validated against original saved planes; no qpos, truth or symbol enters direction',
          'comparison_limit': 'No scene refresh, action or simulation is rerun. CPU plane recovery and unchanged frame fits do not validate runtime stopping or physical task success',
          'records': ref(records), 't8_comparison': ref(t8_path), 'explicit_world_refs': ref(input_path),
          'producer': ref(__file__), 'private_qpos_or_truth_used': False, 'shared_runtime_changed': False,
          'original_labels_changed': False, 'new_model_calls': 0, 'new_physics': 0, 'new_training_rows': 0}
report_path = OUT / 'report.json'
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': ref(report_path), 'same20': report['same20'], 't8_result': report['t8_result'],
                  'new_geometry_nulls_under_v7': new_nulls, 'reproduction_failures': reproduction_failures,
                  'fixed_frame_changes': frame_changes}), flush=True)
