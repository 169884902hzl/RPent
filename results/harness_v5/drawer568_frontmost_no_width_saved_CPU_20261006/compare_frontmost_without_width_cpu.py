"""Compare frontmost ranking with original gates versus v7 width on public data."""

from collections import Counter
from functools import lru_cache
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
V7 = ROOT / 'results/harness_v5/drawer567_frontmost_saved_RGBD_CPU_20261006/comparison'
SOURCE = ROOT / 'source_v5_drawer565_20261006'
sys.path.insert(0, str(SOURCE))
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import measured_fixture_endpoint, vertical_face
spec = importlib.util.spec_from_file_location('frontmost_no_width_cpu', BASE / 'frontmost_no_width_cpu.py')
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)


@lru_cache(maxsize=None)
def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def entity(raw):
    return Entity(**{key: raw[key] for key in Entity.__dataclass_fields__ if key in raw})


def support(cloud, front):
    if not len(cloud):
        return {'points': 0, 'width_m': 0., 'height_m': 0.}
    tangent = np.array([-front[1], front[0]])
    return {'points': len(cloud), 'width_m': float(np.ptp(cloud[:, :2] @ tangent)),
            'height_m': float(np.ptp(cloud[:, 2])), 'lower': np.min(cloud, axis=0).tolist(),
            'upper': np.max(cloud, axis=0).tolist()}


def fit_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    return (a['points'] == b['points'] and np.allclose(a['centre'], b['centre'], atol=1e-12, rtol=0)
            and np.allclose(a['normal_xy'], b['normal_xy'], atol=1e-12, rtol=0)
            and abs(a['residual_p90_m'] - b['residual_p90_m']) <= 1e-12)


def moving_candidates(world, parent, part, current, front, depth_flag):
    tangent = np.array([-front[1], front[0]])
    lower, upper = np.asarray(parent.lower), np.asarray(parent.upper)
    corners = np.array([(x, y) for x in (lower[0], upper[0]) for y in (lower[1], upper[1])])
    side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
    width = float(side_hi - side_lo)
    edge = np.max(corners @ front)
    depth_start = np.min(corners @ front) if depth_flag else edge
    border = min(.025, width * .12)
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    depth, side = points[:, :2] @ front, points[:, :2] @ tangent
    cloud = points[(side >= side_lo + border) & (side <= side_hi - border)
          & (points[:, 2] >= part.lower[2] + .005) & (points[:, 2] <= part.upper[2] - .005)
          & (depth >= depth_start - .03) & (depth <= edge + .35)]
    cloud = cloud[((cloud >= np.asarray(current.lower) - .005)
                   & (cloud <= np.asarray(current.upper) + .005)).all(axis=1)]
    projection = cloud[:, :2] @ front
    histogram, edges = np.histogram(projection, bins=np.arange(depth_start - .031, edge + .356, .004))
    result = []
    for index in np.argsort(histogram)[-5:]:
        centre = (edges[index] + edges[index + 1]) / 2
        selected = cloud[np.abs(projection - centre) <= .004]
        shape = support(selected, front)
        fit = vertical_face(selected) if histogram[index] >= 30 else None
        cosine = abs(float(np.asarray(fit['normal_xy']) @ front)) if fit else None
        original_pass = fit is not None and cosine >= .95
        result.append({'bin': int(index), 'histogram_points': int(histogram[index]),
                       'bin_projection_m': [float(edges[index]), float(edges[index + 1])],
                       'point_support': shape, 'parent_width_m': width,
                       'width_fraction': shape['width_m'] / width,
                       'fit': fit, 'fit_residual_p90_m': fit['residual_p90_m'] if fit else None,
                       'normal_cosine': cosine, 'passes_original_moving_gates': bool(original_pass),
                       'passes_v7_extra_width_gate': shape['width_m'] >= .5 * width,
                       'passes_all_v7_moving_gates': bool(original_pass and shape['width_m'] >= .5 * width),
                       'outward_fit_depth_m': float(np.asarray(fit['centre'][:2]) @ front) if fit else None})
    return result


def compare_capture(original, parent, part, current, front, step, depth_flag=True):
    worlds, views, candidate_rows = [], {}, []
    for camera in ('agentview', 'wrist'):
        old = original['views'][camera]
        path = Path(old['public_RGBD']['path'])
        if ref(str(path))['sha256'] != old['public_RGBD']['sha256']:
            raise ValueError('Original explicit public world changed')
        world = np.load(path)['array']
        worlds.append(world.reshape(-1, 3))
        evidence, clouds = implementation.measured_drawer_faces(world, parent, part, [*front, 0.],
                 moving_part=current, measured_bounds_depth=depth_flag, frontmost_panel=True)
        candidates = moving_candidates(world, parent, part, current, front, depth_flag)
        views[camera] = {'public_RGBD': ref(str(path)), 'frontmost_original_gates': evidence,
                         'selected_support': {key: support(value, front) for key, value in clouds.items()},
                         'v7': old['v7_on']['evidence'], 'moving_candidates': candidates}
        candidate_rows.extend({'view': camera, **candidate} for candidate in candidates)
    joined = np.concatenate(worlds)
    evidence, clouds = implementation.measured_drawer_faces(joined, parent, part, [*front, 0.],
                moving_part=current, measured_bounds_depth=depth_flag, frontmost_panel=True)
    raw_joined = dict(evidence)
    disagreements = {}
    for key in ('frame', 'moving'):
        a, b = [views[camera]['frontmost_original_gates'].get(key) for camera in ('agentview', 'wrist')]
        if a is not None and b is not None:
            normal = np.asarray(a['normal_xy'])
            distance = abs(float((np.asarray(a['centre'][:2]) - b['centre'][:2]) @ normal))
            cosine = abs(float(normal @ b['normal_xy']))
            if distance > .015 or cosine < .95:
                evidence[key] = None
                disagreements[key] = {'normal_distance_m': distance, 'normal_cosine': cosine}
    if disagreements:
        evidence.update(reason='drawer_views_disagree', view_disagreements=disagreements)
    evidence.update(source_step=step, source='perception')
    candidates = moving_candidates(joined, parent, part, current, front, depth_flag)
    candidate_rows.extend({'view': 'joined', **candidate} for candidate in candidates)
    v7 = original['joined_and_original_view_disagreement_gates']['v7_on']['evidence']
    parent_width = max(candidate['parent_width_m'] for candidate in candidates)
    shape = support(clouds['moving'], front)
    return {'views': views, 'joined_candidates': candidates, 'all_candidate_rows': candidate_rows,
            'frontmost_original_gates_raw_joined': raw_joined,
            'frontmost_original_gates_with_original_disagreement_gates': evidence,
            'selected_joined_support': {key: support(value, front) for key, value in clouds.items()},
            'v7': v7, 'v7_selected_support': original['joined_and_original_view_disagreement_gates']['v7_on']['clouds'],
            'selected_moving_width_fraction': shape['width_m'] / parent_width if evidence.get('moving') else None,
            'moving_identical_to_v7': fit_equal(evidence.get('moving'), v7.get('moving')),
            'fixed_frame_identical_to_v7': fit_equal(evidence.get('frame'), v7.get('frame')),
            'crossview_disagreements': disagreements}


OUT.mkdir(exist_ok=False)
rows = list(map(json.loads, (V7 / 'same20_geometry_comparison.jsonl').read_text().splitlines()))
assert len(rows) == 20
items, all_candidates, changes = [], [], []
counts = Counter()
for index, row in enumerate(rows, 1):
    parent, part, current = [entity(row[key]) for key in ('public_initial_parent', 'public_initial_part', 'public_current_part')]
    front = np.asarray(row['public_axis_candidate_xy'])
    item = {'case': row['case'], 'type': row['type'], 'episode': row['episode'], 'state_sha256': row['state_sha256'],
            'axis_candidate_xy': front.tolist(), 'axis_reconstruction_method': row['public_axis_reconstruction_method'],
            'fresh_before_after_public_steps': row['fresh_before_after_public_steps'], 'captures': {}}
    for phase, active_part in [('before', part), ('after', current)]:
        original = row['captures'][phase]
        step = original['joined_and_original_view_disagreement_gates']['v7_on']['evidence']['source_step']
        result = compare_capture(original, parent, part, active_part, front, step)
        item['captures'][phase] = result
        all_candidates.extend({'case': row['case'], 'phase': phase, **candidate} for candidate in result['all_candidate_rows'])
        counts['captured_phase_comparisons'] += 1
        counts['fixed_frame_identical'] += result['fixed_frame_identical_to_v7']
        counts['selected_joined_moving_narrower_than_v7_width_gate'] += result['selected_moving_width_fraction'] is not None and result['selected_moving_width_fraction'] < .5
        if not result['moving_identical_to_v7']:
            change = {'case': row['case'], 'phase': phase, 'v7_moving': result['v7'].get('moving'),
                      'frontmost_original_gates_moving': result['frontmost_original_gates_with_original_disagreement_gates'].get('moving'),
                      'new_selected_support': result['selected_joined_support']['moving'],
                      'new_selected_width_fraction': result['selected_moving_width_fraction'],
                      'crossview_disagreements': result['crossview_disagreements']}
            changes.append(change)
    item['pair_comparison'] = {}
    for mode in ('v7', 'frontmost_original_gates'):
        key = 'v7' if mode == 'v7' else 'frontmost_original_gates_with_original_disagreement_gates'
        before = item['captures']['before'][key]
        after = item['captures']['after'][key]
        verdict, evidence = measured_fixture_endpoint(before, after, 'open' if row['type'] == 'drawer_open' else 'close', drawer=True)
        result = {'original_v5_geometry_verdict_diagnostic': verdict, 'reason': evidence.get('reason')}
        if after.get('frame') is not None and after.get('moving') is not None:
            result['public_signed_cardinal_extension_m'] = float((np.asarray(after['moving']['centre'][:2]) - after['frame']['centre'][:2]) @ front)
        item['pair_comparison'][mode] = result
        counts[mode + '_known_pairs'] += verdict is not None
        counts[mode + '_null_pairs'] += verdict is None
    items.append(item)
    print(json.dumps({'progress': index, 'case': row['case'], 'pair': item['pair_comparison']}), flush=True)

records = OUT / 'same20_frontmost_comparison.jsonl'
records.write_text(''.join(json.dumps(item) + '\n' for item in items))
candidate_file = OUT / 'all_candidate_planes.jsonl'
candidate_file.write_text(''.join(json.dumps(item) + '\n' for item in all_candidates))
table = OUT / 'candidate_planes.tsv'
fields = ['case', 'phase', 'view', 'bin', 'histogram_points', 'points', 'width_m', 'height_m', 'width_fraction',
          'fit_residual_p90_m', 'normal_cosine', 'outward_fit_depth_m', 'passes_original_moving_gates', 'passes_all_v7_moving_gates']
with table.open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter='\t')
    writer.writeheader()
    for item in all_candidates:
        writer.writerow({key: item['point_support'].get(key) if key in ('points', 'width_m', 'height_m') else item.get(key) for key in fields})
report = {'scope': 'Saved exact same20 public RGB-D: frontmost with original fit gates versus v7 additional0.5-width gate; no runtime trial',
          'original_v7_records': ref(V7 / 'same20_geometry_comparison.jsonl'),
          'counterfactual_snapshot': json.loads((BASE / 'counterfactual_snapshot.json').read_text()),
          'dependencies': [ref(SOURCE / 'robots/libero/v5_state.py'), ref(SOURCE / 'robots/libero/v5_verification.py')],
          'registered_cases': 20, 'counts': dict(counts), 'changed_selected_joined_moving_planes': changes,
          'small_patch_interpretation': 'Narrower-than0.5-parent-width selections are reported as public geometric support, not proven misbindings. Width, height, count, normal and residual alone cannot establish object ownership; no private truth calibrates the rank',
          'runtime_gates_scope': 'Both variants retain30points,40mm height,15mm principal lateral spread,8mm residual,0.95 normal cosine, top5 depth bins, current-part binding, fixed-frame and crossview checks',
          'direction_scope': 'Public direction candidates inherit the prior explicit reconstruction; the old actual runtime front axis was not serialized',
          'freshness_scope': 'Two source cases have duplicate step0 and remain unknown as endpoint pairs',
          'candidate_records': ref(candidate_file), 'candidate_table': ref(table), 'comparison_records': ref(records),
          'producer': ref(__file__), 'private_qpos_or_truth_used': False, 'shared_runtime_changed': False,
          'original_labels_changed': False, 'new_model_calls': 0, 'new_physics': 0, 'new_training_rows': 0}
path = OUT / 'report.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': ref(path), 'counts': dict(counts), 'changed_selected_planes': changes}), flush=True)
