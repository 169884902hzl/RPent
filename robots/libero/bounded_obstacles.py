"""One immutable RGB-D index and voxel partition per public capture."""
import hashlib

import numpy as np
from scipy.spatial import cKDTree


def build_obstacles(points):
    """Index original pixels; instance subtraction precedes voxel selection."""
    return {'points': points, 'tree': cKDTree(points), 'instance_labels': {},
            'key': hashlib.sha256(points.tobytes()).hexdigest(), 'subtractions': {}}


def _cloud_key(points):
    return hashlib.sha256(np.ascontiguousarray(points).tobytes()).digest()


def _within(points, members, radius):
    mask = np.zeros(len(points), dtype=bool)
    if len(members):
        near = ((points >= members.min(0)-radius)
                & (points <= members.max(0)+radius)).all(axis=1)
        mask[near] = cKDTree(members).query(points[near],
            distance_upper_bound=np.nextafter(radius, np.inf))[0] <= radius
    return mask


def subtract_instances(structure, target, held, *, held_margin_m):
    """Return exactly the old first-pixel 4 mm voxels after both exclusions.

    Quantise the full capture once. If an excluded pixel was a voxel's first
    member, choose its next surviving member; never erase an entire voxel
    because its representative belonged to the target.
    """
    key = (_cloud_key(target), _cloud_key(held), held_margin_m)
    cache = structure['subtractions']
    if key in cache:
        return cache[key]
    points = structure['points']
    if 'voxel_partition' not in structure:
        cells = np.ascontiguousarray(np.floor(points/.004).astype(int))
        records = cells.view(np.dtype((np.void, cells.dtype.itemsize*3))).reshape(-1)
        _, first, inverse = np.unique(records, return_index=True, return_inverse=True)
        structure['voxel_partition'] = first, inverse
    first, inverse = structure['voxel_partition']
    excluded = _within(points, target, 1e-6) | _within(points, held, held_margin_m)
    indices = first.copy()
    affected = excluded[first]
    if affected.any():
        indices[affected] = len(points)
        candidates = np.flatnonzero(~excluded & affected[inverse])
        np.minimum.at(indices, inverse[candidates], candidates)
    selected = np.sort(indices[indices < len(points)])
    cache[key] = points[selected]
    return cache[key]
