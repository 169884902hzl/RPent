# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Pool public RGB-D samples in a fixed measured world XY grid.

Image crop coordinates move when the wrist camera moves. This development
encoder keeps cell locations fixed by the action's measured fixture bounds.
It uses no simulator joints, object poses, or task predicates.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from zipfile import BadZipFile
import hashlib

import numpy as np
from PIL import Image


PROFILE = "world_xy_grid_v1"


def pool_view(view: dict, measured_bounds: dict, grid: int = 8) -> tuple[np.ndarray, bool]:
    """Return RGB, measured height and occupancy for fixed world grid cells."""
    empty = np.zeros(grid * grid * 5, dtype=np.float32)
    try:
        lower = np.asarray(measured_bounds["lower"], dtype=float)
        upper = np.asarray(measured_bounds["upper"], dtype=float)
        if (lower.shape != (3,) or upper.shape != (3,)
                or not np.isfinite([lower, upper]).all() or np.any(upper < lower)):
            raise ValueError("invalid measured fixture bounds")
        extent = upper - lower
        padding = np.maximum(extent * .25, [.04, .04, .04])
        lo, hi = lower - padding, upper + padding
        image = np.asarray(Image.open(Path(view["raw_rgb"]["path"])).convert("RGB"))
        with np.load(view["raw_world"]["path"], allow_pickle=False) as archive:
            world = np.asarray(archive["array"], dtype=np.float32)
        if world.ndim != 3 or world.shape[-1] != 3 or image.shape[:2] != world.shape[:2]:
            raise ValueError("public RGB-D shape mismatch")
        keep = (np.isfinite(world).all(axis=-1)
                & (world >= lo).all(axis=-1) & (world <= hi).all(axis=-1))
        points = world[keep]
        if len(points) < 100:
            raise ValueError("fixture crop has insufficient measured points")
        colors = image[keep].astype(np.float32) / 255.
        xy = np.floor((points[:, :2] - lo[:2]) / (hi[:2] - lo[:2]) * grid).astype(int)
        xy = np.clip(xy, 0, grid - 1)
        cells = xy[:, 1] * grid + xy[:, 0]
        channels = np.zeros((5, grid * grid), dtype=np.float32)
        for cell in np.unique(cells):
            selected = cells == cell
            channels[:3, cell] = np.mean(colors[selected], axis=0)
            channels[3, cell] = np.clip(
                (np.median(points[selected, 2]) - lower[2]) / max(float(extent[2]), .03), -3, 3)
            channels[4, cell] = 1.
        return channels.ravel(), True
    except (OSError, BadZipFile, KeyError, ValueError, TypeError, IndexError):
        return empty, False


def encoder_identity() -> str:
    """Pin the world-grid transform, independently of a learned checkpoint."""
    return hashlib.sha256((PROFILE + "\n" + inspect.getsource(pool_view)).encode()).hexdigest()
