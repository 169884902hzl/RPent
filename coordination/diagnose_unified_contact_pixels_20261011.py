"""Export public RGB-D pixels behind a rejected full-route contact candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

sys.path.insert(0, os.environ['GRASP_ROUTE_SOURCE'])
from robots.libero.v5_geometric_grasp import panda_geometry


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--line', type=int, default=1)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--approach-opening', type=float, default=.08)
    args = parser.parse_args()
    row = json.loads(args.ledger.read_text().splitlines()[args.line - 1])
    receipt = row['first_attempt']['receipt']
    ranking = receipt['geometric_grasp_rankings'][0]
    candidate = next(c for c in ranking['candidates'] if c['id'] == args.candidate)
    screen = candidate['route_screen']
    directory = Path(row['output_dir'])
    measured_step = ranking['measurement_step']
    target_file = directory / ('analytic_target_' + ranking['entity'] + '.npz') / f'{measured_step:02d}.npz'
    loaded = np.load(target_file)
    target = loaded[loaded.files[0]]
    tree = cKDTree(target)
    geometry = panda_geometry('/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')
    if screen['reason'] == 'closure_sweep_collision':
        position = np.asarray(candidate['xyz'])
        body = Rotation.from_quat(candidate['body_quat_xyzw'])
        opening = screen['closure']['opening_m']
        inflation = .002
    else:
        segment = screen['segments'][-1]
        waypoint_index = len(screen['segments']) - 1
        waypoint = candidate['route'][waypoint_index]
        previous = candidate['route'][max(0, waypoint_index-1)]
        # The first segment retains the current wrist orientation.
        rotation_start = Rotation.from_quat(previous['body_quat_xyzw'])
        rotation_end = Rotation.from_quat(waypoint['body_quat_xyzw'])
        fraction = segment['collision']['fraction']
        body = Slerp([0., 1.], Rotation.from_matrix([rotation_start.as_matrix(), rotation_end.as_matrix()]))(fraction)
        position = np.asarray(segment['collision']['xyz'])
        opening, inflation = args.approach_opening, segment['mesh_inflation_m']
    rotation = body.as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for camera in ('agentview', 'wrist'):
        cloud_file = directory / (camera + '_world_high.npz') / f'{measured_step:02d}.npz'
        loaded = np.load(cloud_file)
        cloud = loaded[loaded.files[0]]
        flat = cloud.reshape(-1, 3)
        near = ((flat >= target.min(axis=0)-1e-6)&(flat <= target.max(axis=0)+1e-6)).all(axis=1)
        distances = np.full(len(flat),np.inf)
        distances[near] = tree.query(flat[near])[0]
        membership = distances <= 1e-6
        local = (flat-position) @ rotation
        collision = np.zeros(len(flat), dtype=bool)
        per_mesh = {}
        for box in geometry['boxes']:
            slide = np.asarray(box.get('slide_per_half_opening', [0,0,0])) * opening/2
            inside = ((local >= np.asarray(box['lower']) + slide - inflation)
                      & (local <= np.asarray(box['upper']) + slide + inflation)).all(axis=1)
            if box.get('convex_halfspaces'):
                equations = np.asarray(box['convex_halfspaces'])
                inside[inside] = (((local[inside]-slide) @ equations[:,:3].T + equations[:,3]) <= inflation).all(axis=1)
            ids = np.flatnonzero(inside & ~membership)
            per_mesh[box['name']] = ids.tolist()
            collision[ids] = True
        ids = np.flatnonzero(collision)
        pixels = np.stack(np.unravel_index(ids, cloud.shape[:2]), axis=1)
        image_file = directory / (camera + '_high.png') / f'{measured_step:02d}.png'
        image = Image.open(image_file).convert('RGB')
        # Cyan marks the measured target silhouette, red marks retained scene collisions.
        from scipy.ndimage import binary_erosion
        silhouette = membership.reshape(cloud.shape[:2])
        edge = silhouette & ~binary_erosion(silhouette)
        rgb = np.asarray(image).copy()
        rgb[edge] = [0,255,255]
        image = Image.fromarray(rgb)
        draw = ImageDraw.Draw(image)
        for y,x in pixels:
            draw.ellipse((int(x)-4,int(y)-4,int(x)+4,int(y)+4), outline='red', width=1)
        image.save(args.output / (camera + '.png'))
        records.append({'camera': camera, 'collision_points': flat[ids].tolist(),
                        'pixels_yx': pixels.tolist(), 'mesh_pixels_flat': per_mesh,
                        'target_nearest_distance_m': tree.query(flat[ids])[0].tolist(),
                        'cloud': pin(cloud_file), 'image': pin(image_file)})
    manifest = {'ledger': pin(args.ledger), 'line': args.line, 'target_cloud': pin(target_file),
                'candidate': candidate, 'views': records,
                'private_target_pose_used': False, 'training_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'reason': screen['reason'], 'views': [{k:v for k,v in r.items() if k not in ('mesh_pixels_flat','cloud','image')} for r in records]}))


if __name__ == '__main__':
    main()
