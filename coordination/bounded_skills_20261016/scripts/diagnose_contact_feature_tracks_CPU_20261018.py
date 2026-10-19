# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measure RGB feature tracks on saved contact surfaces, without controls."""
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import cv2
import numpy as np
from scipy.spatial import cKDTree

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
records = []
for job in ('9502_160', '9504_120'):
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    rows = [json.loads(line) for line in choices.open()]
    motions = [(row, detail['execution']['public_contact_motion']) for row in rows
        for detail in row.get('execution_details', [])
        if detail.get('execution', {}).get('public_contact_motion')][:2]
    for row, motion in motions:
        before, after = motion['before_capture_step'], motion['after_capture_step']
        candidate = next(c for c in row['request']['candidates']
            if c['id'] in row['decision']['candidate_ids'] and c['skill'] == 'nudge')
        key = candidate['parameters']['anchor_id']
        path = choices.parent/f'bounded_contact_{key}_reference.npz'/f'{before:02d}.npz'
        with np.load(path) as arrays:
            reference = arrays[arrays.files[0]]
        tree = cKDTree(reference)
        for camera in ('agentview', 'wrist'):
            files, worlds, images = [], [], []
            for step in (before, after):
                depth = choices.parent/f'{camera}_world_high.npz'/f'{step:02d}.npz'
                image = choices.parent/f'{camera}_high.png'/f'{step:02d}.png'
                files += [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in (depth, image)]
                with np.load(depth) as arrays:
                    worlds.append(arrays[arrays.files[0]])
                images.append(cv2.imread(str(image)))
            world = worlds[0]
            flat = world.reshape(-1, 3)
            inside = np.isfinite(flat).all(1) & (flat >= reference.min(0)-1e-6).all(1) & (flat <= reference.max(0)+1e-6).all(1)
            ids = np.flatnonzero(inside)
            mask = np.zeros(len(flat), np.uint8)
            mask[ids[tree.query(flat[ids], distance_upper_bound=1e-6)[0] <= 1e-6]] = 255
            mask = mask.reshape(world.shape[:2])
            gray = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in images]
            corners = cv2.goodFeaturesToTrack(gray[0], maxCorners=200,
                qualityLevel=.01, minDistance=3, mask=mask, blockSize=5)
            record = {'job': job, 'row': row['index'], 'camera': camera,
                'before_capture_step': before, 'after_capture_step': after,
                'original_motion': motion, 'reference': {'path': str(path),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, 'files': files,
                'masked_pixels': int((mask > 0).sum()), 'detected_corners': 0 if corners is None else len(corners)}
            if corners is not None:
                tracked, status, error = cv2.calcOpticalFlowPyrLK(gray[0], gray[1], corners, None,
                    winSize=(21, 21), maxLevel=3)
                backward, back_status, _ = cv2.calcOpticalFlowPyrLK(gray[1], gray[0], tracked, None,
                    winSize=(21, 21), maxLevel=3)
                first, second = corners[:, 0], tracked[:, 0]
                valid = (status[:, 0] > 0) & (back_status[:, 0] > 0)
                valid &= np.linalg.norm(backward[:, 0]-first, axis=1) <= .5
                valid &= error[:, 0] <= 20
                coordinates = [np.rint(x).astype(int) for x in (first, second)]
                for points, depth in zip(coordinates, worlds):
                    valid &= (points[:, 0] >= 0) & (points[:, 0] < depth.shape[1]) & (points[:, 1] >= 0) & (points[:, 1] < depth.shape[0])
                kept = np.flatnonzero(valid)
                points = [depth[xy[kept, 1], xy[kept, 0]] for xy, depth in zip(coordinates, worlds)]
                delta = points[1]-points[0]
                finite = np.isfinite(delta).all(1) & (np.linalg.norm(delta, axis=1) <= .05)
                kept, delta = kept[finite], delta[finite]
                record.update(valid_tracks=len(kept), tracks_before_px=first[kept].tolist(),
                    tracks_after_px=second[kept].tolist(), track_displacements_m=delta.tolist(),
                    median_displacement_m=np.median(delta, axis=0).tolist() if len(delta) else None,
                    q10_q90_displacement_m=np.quantile(delta, [.1, .9], axis=0).tolist() if len(delta) else None)
                canvas = images[1].copy()
                for a, b in zip(first[kept], second[kept]):
                    cv2.line(canvas, tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int)), (0, 0, 255), 1)
                    cv2.circle(canvas, tuple(np.rint(b).astype(int)), 2, (0, 255, 0), -1)
                overlay = base/'reports'/f'contact_tracks_r2_{job}_row{row["index"]}_{before}_{after}_{camera}.png'
                cv2.imwrite(str(overlay), canvas)
                record['overlay'] = {'path': str(overlay), 'sha256': hashlib.sha256(overlay.read_bytes()).hexdigest()}
            records.append(record)
            print(json.dumps({k: record.get(k) for k in ('job', 'row', 'camera', 'masked_pixels',
                'detected_corners', 'valid_tracks', 'median_displacement_m', 'q10_q90_displacement_m')}), flush=True)
output = base/'reports/contact_feature_tracks_CPU_20261018_r2.json'
output.write_text(json.dumps({'records': records, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'physics_steps': 0, 'gpu_used': False, 'training': False,
    'scope': 'saved public RGB-D diagnostics; feature tracks are not a validated runtime verifier'}, indent=2)+'\n')
