"""Replay public RGB-D geometry and binding, without SAM or physical execution."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from robots.libero.v5_fixture_parts import measured_drawer_faces, measured_drawer_handle, measured_microwave_door
from robots.libero.v5_state import Candidate, Entity
from robots.libero.v5_subtasks import subtask_prompt, SubtaskBindingError
from robots.libero.v5_verification import vertical_face

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
JOB = ROOT / 'results/harness_v5/fixture540_measured_handle_selection/source547_smoke30/job4150/part0'
DEST = ROOT / 'results/harness_v5/runtime542_readonly_audit_CPU_20261006'
CASES = ['drawer_close_libero_90_t0_s11_r0_articulate_measured_fixture_handle160',
         'microwave_open_libero_90_t33_s2_r0_articulate_measured_fixture_handle160',
         'microwave_close_libero_90_t33_s3_r0_articulate_measured_fixture_handle160']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entity(record):
    return Entity(**{key: record[key] for key in
        ('id', 'name', 'xyz', 'lower', 'upper', 'visible', 'source_step', 'part_of', 'geometry')})


def array(path):
    with np.load(path) as archive:
        return archive[archive.files[0]].astype(float)


def projection(cloud, metadata, world):
    transform = np.linalg.inv(np.asarray(metadata['extrinsic_cam2world']))
    points = (np.c_[cloud, np.ones(len(cloud))] @ transform.T)[:, :3]
    homogeneous = points @ np.asarray(metadata['intrinsic_K']).T
    pixels = homogeneous[:, :2] / homogeneous[:, 2:3]
    inside = ((points[:, 2] > 0) & (pixels[:, 0] >= 0) & (pixels[:, 0] < metadata['width'])
              & (pixels[:, 1] >= 0) & (pixels[:, 1] < metadata['height']))
    scaled = pixels[inside] * [world.shape[1] / metadata['width'], world.shape[0] / metadata['height']]
    indices = scaled.astype(int)
    current = world[indices[:, 1], indices[:, 0]]
    current_camera = (np.c_[current, np.ones(len(current))] @ transform.T)[:, :3]
    finite = np.isfinite(current).all(axis=1) & (np.abs(current).sum(axis=1) > 1e-6)
    difference = points[inside, 2] - current_camera[:, 2]
    return {'points': len(cloud), 'in_view_fraction': float(inside.mean()),
            'pixels_p05_p95': np.quantile(pixels, [.05, .95], axis=0).tolist(),
            'current_depth_samples': int(finite.sum()),
            'same_world_support_6mm': int(np.count_nonzero(finite & (np.linalg.norm(current-cloud[inside], axis=1) <= .006))),
            'nearer_measured_surface': int(np.count_nonzero(finite & (difference > .006))),
            'farther_measured_surface': int(np.count_nonzero(finite & (difference < -.006))),
            'scope': 'Projection of previously measured support; no current semantic mask is assumed.'}


report = {'scope': 'SOURCE547 public-only CPU geometry/binding; immutable three registered part0 attempts. '
                   'No SAM/model/physics calls, no truth supplied to geometry.', 'records': []}
montage = Image.new('RGB', (1024, 3 * 286), '#222222')
draw = ImageDraw.Draw(montage)
for index, case in enumerate(CASES):
    episode = JOB / case / 'attempt0'
    raw = episode / 'private_skill_diagnostic.json'
    data = json.loads(raw.read_text())
    assert data['case']['name'] == case
    first = data['first_attempt']
    public = [entity(e) for e in first['public_before']['entities']]
    by_id = {e.id: e for e in public}
    selected = by_id[re.match(r'articulate\((e[0-9]+),', first['selected'])[1]]
    states_path = episode / 'states.json'
    states = json.loads(states_path.read_text())
    registered = {entry['step_idx']: entry['artifacts'] for entry in states['steps']}
    frames = sorted(registered)
    detail = {'case': case, 'input': {'path': str(raw), 'sha256': sha(raw)},
              'states': {'path': str(states_path), 'sha256': sha(states_path)},
              'selected': first['selected'], 'receipt': {k: first['receipt'].get(k) for k in
                    ('verification', 'failure_reason', 'articulate_verified', 'chunks')},
              'public_entities': first['public_before']['entities'], 'geometry': []}
    draw.text((4, index * 286 + 2), case, fill='white')
    for column, (frame, view) in enumerate((f, v) for f in (frames[0], frames[-1]) for v in ('agentview', 'wrist')):
        image_name, world_name, metadata_name = f'{view}_high.png', f'{view}_world_high.npz', f'{view}_metadata.json'
        assert all(name in registered[frame] for name in (image_name, world_name, metadata_name))
        image_path = episode / image_name / f'{frame:02d}.png'
        image = Image.open(image_path).convert('RGB')
        montage.paste(image.resize((256, 256)), (column * 256, index * 286 + 28))
        draw.text((column * 256 + 4, index * 286 + 14), f'frame{frame} {view}', fill='white')
        if 'drawer_close' in case:
            parent = by_id[selected.part_of]
            axis = first['receipt']['fixture_handle_approach']['before']['pose']['approach_normal_xy']
            world_path = episode / world_name / f'{frame:02d}.npz'
            metadata_path = episode / metadata_name / f'{frame:02d}.json'
            world = array(world_path)
            metadata = json.loads(metadata_path.read_text())
            pose, evidence, handle_cloud = measured_drawer_handle(world, parent, selected, axis)
            faces, face_clouds = measured_drawer_faces(world, parent, selected, axis)
            # The prior public camera cloud and exact RGB-D face function are
            # the basis of the FoV/occlusion calculation; no simulation pose.
            prior = first['receipt']['fixture_handle_approach']['before']['views']['wrist']['cloud']
            assert sha(Path(prior['path'])) == prior['sha256']
            previous_handle = array(prior['path'])
            prior_world = array(episode / 'wrist_world_high.npz' / '00.npz')
            _, prior_faces = measured_drawer_faces(prior_world, parent, selected, axis)
            detail['geometry'].append({'frame': frame, 'view': view, 'pose': pose,
                'handle_evidence': evidence, 'face_evidence': faces,
                'prior_handle_projection': projection(previous_handle, metadata, world),
                'prior_moving_face_projection': projection(prior_faces['moving'], metadata, world),
                'world_sha256': sha(world_path), 'metadata_sha256': sha(metadata_path)})
    if 'microwave' in case:
        try:
            detail['subtask_binding'] = {'prompt': subtask_prompt(
                Candidate('vla_subtask', selected.id, mode=data['case']['mode']), public)}
        except SubtaskBindingError as error:
            detail['subtask_binding'] = {'error': str(error)}
        for frame, names in registered.items():
            for name in names:
                if not name.startswith('microwave_door_') or not name.endswith('.npz'):
                    continue
                path = episode / name / f'{frame:02d}.npz'
                cloud = array(path)
                parent_id = re.match(r'microwave_door_(e[0-9]+)_', name)[1]
                parent = by_id[parent_id]
                door, evidence = measured_microwave_door(parent, cloud)
                detail['geometry'].append({'frame': frame, 'registered_door_cloud': str(path),
                    'sha256': sha(path), 'parent': parent_id,
                    'current_for_selected_parent': frame == selected.source_step and parent_id == selected.id,
                    'face': vertical_face(cloud), 'door_geometry': door, 'door_gate': evidence})
        detail['handle_measurement'] = first['receipt']['fixture_handle_approach']['before']
    report['records'].append(detail)

image_path = DEST / 'job4150_precontact_public_views.png'
montage.save(image_path)
report['montage'] = {'path': str(image_path), 'sha256': sha(image_path)}
out = DEST / 'job4150_precontact_geometry_CPU.json'
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': str(out), 'sha256': sha(out), 'cases': [r['case'] for r in report['records']]}))
