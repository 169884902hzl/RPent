"""Eight explicit public capture chains; no semantic or physical re-execution."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
DEST = ROOT / 'results/harness_v5/runtime550_closed_microwave_CPU_20261006'
MANIFEST = DEST / 'explicit8_public_cases.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array(path):
    with np.load(path) as data:
        return data[data.files[0]].astype(float)


def project(points, metadata, world):
    transform = np.linalg.inv(np.asarray(metadata['extrinsic_cam2world']))
    xyz = (np.c_[points, np.ones(len(points))] @ transform.T)[:, :3]
    homogeneous = xyz @ np.asarray(metadata['intrinsic_K']).T
    positive = xyz[:, 2] > 0
    pixels = np.full((len(points), 2), np.inf)
    pixels[positive] = homogeneous[positive, :2] / homogeneous[positive, 2:3]
    inside = (positive & (pixels[:, 0] >= 0) & (pixels[:, 0] < metadata['width'])
              & (pixels[:, 1] >= 0) & (pixels[:, 1] < metadata['height']))
    indices = (pixels[inside] * [world.shape[1] / metadata['width'], world.shape[0] / metadata['height']]).astype(int)
    samples = world[indices[:, 1], indices[:, 0]]
    valid = np.isfinite(samples).all(axis=1) & (np.abs(samples).sum(axis=1) > 1e-6)
    sample_xyz = (np.c_[samples, np.ones(len(samples))] @ transform.T)[:, :3]
    depth_diff = xyz[inside, 2] - sample_xyz[:, 2]
    return {'points': len(points), 'in_view_fraction': float(inside.mean()),
            'same_world_support_6mm': int(np.count_nonzero(valid & (np.linalg.norm(samples-points[inside], axis=1) <= .006))),
            'nearer_depth_support': int(np.count_nonzero(valid & (depth_diff > .006))),
            'farther_depth_support': int(np.count_nonzero(valid & (depth_diff < -.006))),
            'note': 'Prior microwave cloud can include its moving door; changed depth is not evidence of semantic recall failure.'}


manifest = json.loads(MANIFEST.read_text())
report = {'scope': 'Eight explicit SOURCE544 setup capture chains. Public RGB-D, public entities and original registered clouds only. '
          'No BDDL/true object or joint coordinate, SAM call, planner, physical execution or score change.',
          'manifest': {'path': str(MANIFEST), 'sha256': sha(MANIFEST)}, 'records': []}
montage = Image.new('RGB', (1024, 8 * 280), '#222222')
draw = ImageDraw.Draw(montage)
for index, item in enumerate(manifest['records']):
    episode = Path(item['episode'])
    states_path = episode / 'states.json'
    states = json.loads(states_path.read_text())
    registered = {row['step_idx']: row['artifacts'] for row in states['steps']}
    assert set(registered) == {0, 1}
    before = [entity for entity in item['public_before']['entities'] if entity['name'] == 'microwave']
    after = [entity for entity in item['public_after']['entities'] if entity['name'] == 'microwave']
    assert len(before) == len(after) == 1
    parent = before[0]
    cloud_names = [name for name in registered[0] if name.startswith('fixture_points_' + parent['id'] + '_')]
    assert len(cloud_names) == 1
    cloud_path = episode / cloud_names[0] / '00.npz'
    cloud = array(cloud_path)
    record = {'case': item['case'], 'selected': item['selected'],
              'states': {'path': str(states_path), 'sha256': sha(states_path)},
              'same_public_id': before[0]['id'] == after[0]['id'],
              'before_parent': before[0], 'after_parent': after[0],
              'registered_prior_cloud': {'path': str(cloud_path), 'sha256': sha(cloud_path)},
              'registered_sam_mask_artifacts': [name for frame in registered.values() for name in frame if name.startswith('v6_sam_')],
              'receipt_verification': item['receipt']['verification'],
              'receipt_reason': item['receipt'].get('reason'), 'captures': []}
    draw.text((3, index * 280 + 2), item['case'], fill='white')
    for column, (frame, view) in enumerate((frame, view) for frame in (0, 1) for view in ('agentview', 'wrist')):
        names = [f'{view}_high.png', f'{view}_world_high.npz', f'{view}_metadata.json']
        assert all(name in registered[frame] for name in names)
        image_path = episode / names[0] / f'{frame:02d}.png'
        world_path = episode / names[1] / f'{frame:02d}.npz'
        metadata_path = episode / names[2] / f'{frame:02d}.json'
        image = Image.open(image_path).convert('RGB')
        montage.paste(image.resize((256, 256)), (column * 256, index * 280 + 24))
        draw.text((column * 256 + 3, index * 280 + 12), f'frame{frame} {view}', fill='white')
        world, metadata = array(world_path), json.loads(metadata_path.read_text())
        current = world.reshape(-1, 3)
        valid = np.isfinite(current).all(axis=1) & (np.abs(current).sum(axis=1) > 1e-6)
        inside = ((current >= np.asarray(parent['lower']) - .006)
                  & (current <= np.asarray(parent['upper']) + .006)).all(axis=1)
        record['captures'].append({'frame': frame, 'camera': view,
            'inputs': [{'path': str(path), 'sha256': sha(path)} for path in (image_path, world_path, metadata_path)],
            'current_points_in_old_parent_aabb': int(np.count_nonzero(valid & inside)),
            'prior_cloud_projection': project(cloud, metadata, world)})
    report['records'].append(record)
image_path = DEST / 'closed_microwave8_public_views.png'
montage.save(image_path)
report['montage'] = {'path': str(image_path), 'sha256': sha(image_path)}
destination = DEST / 'closed_microwave8_capture_audit_CPU.json'
destination.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': str(destination), 'sha256': sha(destination),
    'old_id_preserved': sum(row['same_public_id'] for row in report['records']),
    'saved_sam_masks': sum(len(row['registered_sam_mask_artifacts']) for row in report['records']),
    'frame1_views': [{'case': row['case'], 'views': [{'camera': cap['camera'],
       'old_aabb_support': cap['current_points_in_old_parent_aabb'], 'old_cloud': cap['prior_cloud_projection']}
        for cap in row['captures'] if cap['frame'] == 1]} for row in report['records']]}))
