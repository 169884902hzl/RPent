"""Explain one saved moving-plane choice from public RGB-D only, on CPU."""

import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_drawer558_20261006'
FINAL = Path(__file__).resolve().parent / 'final_20261006T164608.567363Z'
LEDGER = FINAL / 'statistic/preparation/ledger_00.jsonl'
CASE = 'drawer559_drawer_open_libero90_t8_s18_r0_native_original160'
sys.path.insert(0, str(SOURCE))
from robots.libero.v5_fixture_parts import measured_drawer_faces
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import vertical_face


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def entity(raw):
    return Entity(**{key: raw[key] for key in Entity.__dataclass_fields__ if key in raw})


def stats(points):
    if not len(points):
        return {'points': 0}
    return {'points': len(points), 'lower': np.min(points, axis=0).tolist(),
            'upper': np.max(points, axis=0).tolist(),
            'quantile05_50_95': np.quantile(points, [.05, .5, .95], axis=0).tolist()}


row = next(json.loads(line) for line in LEDGER.read_text().splitlines()
           if json.loads(line)['case']['name'] == CASE)
first = row['first_attempt']
metrology = first['verification_measurements']['articulation']
before = {item['id']: item for item in first['public_before']['entities']}
after = {item['id']: item for item in first['public_after']['entities']}
parent = entity(before[metrology['before']['anchor_parent']])
part = entity(before[metrology['before']['anchor_part']])
current = entity(after[metrology['after']['current_part']])
# SOURCE558 did not serialize its front_axis. This candidate is inferred
# only from the saved public frame normal and initial public EEF side, and
# validated below against the saved per-camera moving-plane result.
normal = np.asarray(metrology['before']['frame']['normal_xy'])
eef = np.asarray(first['public_before']['robot']['eef_xyz'])
side = float((eef[:2] - metrology['before']['frame']['centre'][:2]) @ normal)
outward = normal if side > 0 else -normal
front = np.zeros(2)
front[np.argmax(np.abs(outward))] = np.sign(outward[np.argmax(np.abs(outward))])
tangent = np.array([-front[1], front[0]])
lower, upper = np.asarray(parent.lower), np.asarray(parent.upper)
corners = np.array([(x, y) for x in (lower[0], upper[0]) for y in (lower[1], upper[1])])
side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
edge = np.max(corners @ front)
border_width = min(.025, (side_hi - side_lo) * .12)
bins = np.arange(edge - .031, edge + .356, .004)
views = {}
for camera in ('agentview', 'wrist'):
    path = Path(row['output_dir']) / f'{camera}_world_high.npz/01.npz'
    points = np.asarray(np.load(path)['array'], dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    depth, lateral = points[:, :2] @ front, points[:, :2] @ tangent
    gate = ((lateral >= side_lo + border_width) & (lateral <= side_hi - border_width)
            & (points[:, 2] >= part.lower[2] + .005) & (points[:, 2] <= part.upper[2] - .005)
            & (depth >= edge - .03) & (depth <= edge + .35))
    unbound = points[gate]
    cloud = unbound[((unbound >= np.asarray(current.lower) - .005)
                     & (unbound <= np.asarray(current.upper) + .005)).all(axis=1)]
    projection = cloud[:, :2] @ front
    histogram, edges = np.histogram(projection, bins=bins)
    top5 = np.argsort(histogram)[-5:].tolist()
    candidates = []
    for index, count in enumerate(histogram):
        if count < 30:
            continue
        centre = (edges[index] + edges[index + 1]) / 2
        selected = cloud[np.abs(projection - centre) <= .004]
        fit = vertical_face(selected)
        normal_match = fit is not None and abs(np.asarray(fit['normal_xy']) @ front) >= .95
        xy = selected[:, :2]
        candidates.append({'bin': index, 'bin_depth_m': [float(edges[index]), float(edges[index + 1])],
                           'histogram_points': int(count), 'top5_examined_by_runtime': index in top5,
                           'selected_cloud': stats(selected), 'height_span_m': float(np.ptp(selected[:, 2])),
                           'tangent_span_m': float(np.ptp(xy @ tangent)),
                           'fit': fit, 'normal_passes_original_gate': bool(normal_match),
                           'passes_original_fit_gates': bool(normal_match)})
    replay, replay_clouds = measured_drawer_faces(points, parent, part, [*front, 0.], moving_part=current)
    saved = metrology['after']['views'][camera]['moving']
    produced = replay['moving']
    match = saved is None and produced is None
    if saved is not None and produced is not None:
        match = (saved['points'] == produced['points']
                 and np.allclose(saved['centre'], produced['centre'], atol=1e-12)
                 and np.allclose(saved['normal_xy'], produced['normal_xy'], atol=1e-12))
    views[camera] = {'public_RGBD': ref(path), 'raw_cloud': stats(points),
                     'unbound_moving_gate': stats(unbound), 'current_part_bound_gate': stats(cloud),
                     'top5_histogram_bins_in_runtime_order': top5, 'candidates': candidates,
                     'frozen_function_cpu_result': replay, 'saved_per_camera_moving': saved,
                     'reproduces_saved_moving_exactly': bool(match),
                     'selected_moving_cloud': stats(replay_clouds['moving'])}
frame, moving = metrology['after']['frame'], metrology['after']['moving']
public_upper = float(np.max(np.array([(x, y) for x in (current.lower[0], current.upper[0])
                                     for y in (current.lower[1], current.upper[1])]) @ front))
selected_projection = float(np.asarray(moving['centre'][:2]) @ front)
output = {'scope': 'Exact old4254 t8/s18 public RGB-D CPU diagnosis; no qpos, simulator, replay or relabel',
          'case': CASE, 'captured_ledger': ref(LEDGER), 'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'),
                                                                 'sha256': row['choices_sha256']},
          'producer': ref(__file__), 'frozen_sources': [ref(SOURCE / 'robots/libero/v5_fixture_parts.py'),
                                                      ref(SOURCE / 'robots/libero/v5_verification.py')],
          'public_initial_parent': before[parent.id], 'public_initial_part': before[part.id],
          'public_current_part': after[current.id], 'saved_after_frame': frame, 'saved_after_moving': moving,
          'front_axis_scope': 'Original runtime front_axis absent. Public-normal/EEF-side cardinal candidate is accepted only as a CPU reproduction assumption, not restored serialized runtime evidence',
          'inferred_public_axis_xyz': [*front.tolist(), 0.], 'public_before_eef_normal_side_m': side,
          'public_forward_bound_minus_selected_plane_m': public_upper - selected_projection,
          'views': views, 'private_coordinates_read': False, 'runtime_changed': False,
          'new_model_calls': 0, 'new_physics': 0, 'original_labels_preserved': True}
path = FINAL / 't8s18_public_plane_analysis.json'
path.write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'report': ref(path), 'axis': output['inferred_public_axis_xyz'],
                  'public_forward_bound_minus_selected_plane_m': output['public_forward_bound_minus_selected_plane_m'],
                  'views': {key: {'gate': value['current_part_bound_gate'], 'reproduced': value['reproduces_saved_moving_exactly'],
                                   'candidates': value['candidates']} for key, value in views.items()}}))
