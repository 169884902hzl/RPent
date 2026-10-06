"""Crop masks remain tied to the actual saved full-frame public XYZ pixels."""

import numpy as np
from crop_mapping import crop_rgb, crop_mask_to_full, measured_crop_points


def test_crop_pixels_intrinsics_and_world_points_keep_one_coordinate_mapping():
    image = np.zeros((10, 12, 3), np.uint8)
    metadata = {'width': 12, 'height': 10, 'intrinsic_K': [[20., 0., 6.], [0., 20., 5.], [0., 0., 1.]],
                'extrinsic_cam2world': np.eye(4).tolist()}
    crop, mapping = crop_rgb(image, metadata, [2, 3, 6, 7], longest_edge=8)
    assert crop.shape == (8, 8, 3)
    point = np.array([.01, .02, .5])
    full = np.asarray(mapping['original_high_resolution_intrinsic_K']) @ point
    direct = np.asarray(mapping['crop_intrinsic_K']) @ point
    transformed = np.asarray(mapping['pixel_centres_full_to_crop']) @ (full / full[2])
    assert np.allclose(direct / direct[2], transformed)
    mask = np.zeros((8, 8), bool); mask[:4, :4] = True
    restored = crop_mask_to_full(mask, mapping)
    expected = np.zeros((10, 12), bool); expected[3:5, 2:4] = True
    assert np.array_equal(restored, expected)
    world = np.arange(10 * 12 * 3).reshape(10, 12, 3) + 1.
    points, restored = measured_crop_points(world, mask, mapping)
    assert np.array_equal(points, world[expected])
    assert np.asarray(mapping['extrinsic_cam2world']).tolist() == metadata['extrinsic_cam2world']
