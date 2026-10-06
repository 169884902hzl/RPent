"""Project one registered measured drawer face under hypothetical vertical lifts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_fixture_parts import measured_drawer_faces
from robots.libero.v5_state import Entity

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
CASE = ROOT / 'results/harness_v5/fixture540_measured_handle_selection/source547_smoke30/job4150/part0/drawer_close_libero_90_t0_s11_r0_articulate_measured_fixture_handle160/attempt0'
DEST = ROOT / 'results/harness_v5/runtime542_readonly_audit_CPU_20261006'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_array(path):
    with np.load(path) as data:
        return data[data.files[0]].astype(float)


def view_projection(points, camera, intrinsic, width, height):
    transform = np.linalg.inv(camera)
    xyz = (np.c_[points, np.ones(len(points))] @ transform.T)[:, :3]
    homogeneous = xyz @ intrinsic.T
    pixels = homogeneous[:, :2] / homogeneous[:, 2:3]
    positive = xyz[:, 2] > 0
    inside = (positive & (pixels[:, 0] >= 0) & (pixels[:, 0] < width)
              & (pixels[:, 1] >= 0) & (pixels[:, 1] < height))
    central = (positive & (pixels[:, 0] >= .1 * width) & (pixels[:, 0] < .9 * width)
               & (pixels[:, 1] >= .1 * height) & (pixels[:, 1] < .9 * height))
    return {'points': len(points), 'positive_depth_fraction': float(positive.mean()),
            'in_view_fraction': float(inside.mean()), 'central_80pct_fraction': float(central.mean()),
            'pixels_p05_p95': np.quantile(pixels, [.05, .95], axis=0).tolist()}


raw_path, states_path = CASE / 'private_skill_diagnostic.json', CASE / 'states.json'
raw = json.loads(raw_path.read_text())
states = json.loads(states_path.read_text())
registered = {entry['step_idx']: entry['artifacts'] for entry in states['steps']}
assert 0 in registered and 1 in registered
required = ['wrist_world_high.npz', 'wrist_metadata.json']
assert all(name in registered[frame] for frame in (0, 1) for name in required)
first = raw['first_attempt']
public = {item['id']: Entity(**{key: item[key] for key in
          ('id', 'name', 'xyz', 'lower', 'upper', 'visible', 'source_step', 'part_of', 'geometry')})
          for item in first['public_before']['entities']}
part = next(item for item in public.values() if item.name == 'cabinet top drawer')
parent = public[part.part_of]
approach = first['receipt']['fixture_handle_approach']
axis = approach['before']['pose']['approach_normal_xy']
world_path = CASE / 'wrist_world_high.npz/00.npz'
metadata_path = CASE / 'wrist_metadata.json/01.json'
face, clouds = measured_drawer_faces(load_array(world_path), parent, part, axis)
assert face['moving'] and len(clouds['moving']) > 30
handle = approach['before']['views']['wrist']['cloud']
assert sha(Path(handle['path'])) == handle['sha256']
handle_points = load_array(handle['path'])
metadata = json.loads(metadata_path.read_text())
camera = np.asarray(metadata['extrinsic_cam2world'], dtype=float)
intrinsic = np.asarray(metadata['intrinsic_K'], dtype=float)
records = []
for lift in np.round(np.arange(0, .255, .005), 3):
    trial = camera.copy()
    trial[2, 3] += lift
    records.append({'vertical_lift_m': float(lift),
        'camera_xyz_world': trial[:3, 3].tolist(),
        'moving_face': view_projection(clouds['moving'], trial, intrinsic, metadata['width'], metadata['height']),
        'handle': view_projection(handle_points, trial, intrinsic, metadata['width'], metadata['height'])})
qualified = [item for item in records if item['moving_face']['central_80pct_fraction'] >= .95
             and item['handle']['central_80pct_fraction'] >= .95]
report = {'scope': 'One registered SOURCE547 original-task development attempt. Public RGB-D only. '
          'No simulator pose/BDDL/SAM/physical call. Hypothetical camera translates only along world z; '
          'xy standoff and orientation unchanged. Old cloud projection is not current measurement evidence.',
          'inputs': [{'path': str(path), 'sha256': sha(path)} for path in (raw_path, states_path, world_path, metadata_path)],
          'handle_cloud': handle, 'selected_public_part': part.id,
          'current_camera_xyz_world': camera[:3, 3].tolist(),
          'current_optical_forward_world': camera[:3, 2].tolist(),
          'measured_face': face['moving'],
          'selection_rule': 'smallest 5mm lift placing >=95pct of prior moving-face and handle points in central 80pct image; '
          'runtime must recapture and remeasure, preserving original plane/depth guards',
          'smallest_qualified_lift': qualified[0] if qualified else None,
          'records': records}
destination = DEST / 'job4150_drawer_observation_pose_CPU.json'
destination.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': str(destination), 'sha256': sha(destination),
      'smallest_qualified_lift': report['smallest_qualified_lift'], 'baseline': records[0]}))
