# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public depth storage must preserve the precision needed near finger pads."""

from types import SimpleNamespace

import numpy as np

from robots.libero.tools import _save_observation_artifacts


def test_both_high_resolution_world_maps_preserve_submillimetre_depth():
    depth = np.full((2, 2), 1.0621514, dtype=np.float32)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    meta = {'intrinsic_K': np.eye(3).tolist(),
            'extrinsic_cam2world': np.eye(4).tolist()}
    env = SimpleNamespace(get_camera_meta=lambda *args, **kwargs: meta,
                          render_camera=lambda **kwargs: (rgb, depth))
    primitives = SimpleNamespace(env=env, _last_obs={'main_images': rgb})
    saved = {}

    def save(name, value, **kwargs):
        saved[name] = value

    _save_observation_artifacts(primitives, SimpleNamespace(save=save), 3, {})

    # FP16 rounds this depth by more than 0.1 mm before any grasp measurement.
    assert abs(float(depth[0, 0]) - float(np.float16(depth[0, 0]))) > .0001
    for camera in ('agentview', 'wrist'):
        world = saved[f'{camera}_world_high.npz']
        np.testing.assert_allclose(world[..., 2], depth[::-1], atol=1e-6, rtol=0)
