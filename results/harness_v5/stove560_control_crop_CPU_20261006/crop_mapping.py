"""CPU crop geometry: remap segmented pixels to unchanged calibrated RGB-D."""

import numpy as np
from PIL import Image


VERSION = 'public_rgbd_crop_mapping/1-dev'


def mask_bbox(mask):
    rows, columns = np.nonzero(mask)
    if not len(rows):
        return None
    return [int(columns.min()), int(rows.min()), int(columns.max()) + 1, int(rows.max()) + 1]


def padded_roi(box, image_size, *, fraction=.25, minimum_px=20):
    """Pad a public coarse fixture box, without selecting a private control."""
    width, height = image_size
    x0, y0, x1, y1 = box
    pad_x = max(minimum_px, int(np.ceil((x1 - x0) * fraction)))
    pad_y = max(minimum_px, int(np.ceil((y1 - y0) * fraction)))
    return [max(0, x0 - pad_x), max(0, y0 - pad_y), min(width, x1 + pad_x), min(height, y1 + pad_y)]


def crop_rgb(image, metadata, roi, *, longest_edge=1024):
    """Resize only RGB; preserve full-frame calibration and an explicit map."""
    image = Image.fromarray(np.asarray(image, dtype=np.uint8))
    x0, y0, x1, y1 = roi
    if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
        raise ValueError('crop ROI must be a nonempty full-frame pixel rectangle')
    crop_width, crop_height = x1 - x0, y1 - y0
    scale = longest_edge / max(crop_width, crop_height)
    width, height = max(1, round(crop_width * scale)), max(1, round(crop_height * scale))
    sx, sy = width / crop_width, height / crop_height
    intrinsic = np.asarray(metadata['intrinsic_K'], dtype=float).copy()
    intrinsic[0] *= image.width / metadata['width']
    intrinsic[1] *= image.height / metadata['height']
    # PIL resize maps pixel centres: crop index u -> x0 + (u+.5)/sx-.5.
    forward = np.array([[sx, 0., sx * (.5 - x0) - .5],
                        [0., sy, sy * (.5 - y0) - .5], [0., 0., 1.]])
    mapping = {'version': VERSION, 'roi_xyxy_full_frame': roi,
               'original_size': [image.width, image.height], 'crop_size': [width, height],
               'scale_xy': [sx, sy], 'pixel_centres_full_to_crop': forward.tolist(),
               'pixel_centres_crop_to_full': np.linalg.inv(forward).tolist(),
               'original_high_resolution_intrinsic_K': intrinsic.tolist(),
               'crop_intrinsic_K': (forward @ intrinsic).tolist(),
               'extrinsic_cam2world': metadata['extrinsic_cam2world'],
               'depth_policy': 'No depth interpolation or reconstruction: resize SAM mask back to ROI then index original world map'}
    return np.asarray(image.crop(roi).resize((width, height), Image.Resampling.BICUBIC)), mapping


def crop_mask_to_full(mask, mapping):
    """Return a full-frame boolean mask aligned to the original world map."""
    mask = np.asarray(mask, dtype=bool)
    width, height = mapping['crop_size']
    if mask.shape != (height, width):
        raise ValueError('SAM crop mask must match registered resized crop pixels')
    x0, y0, x1, y1 = mapping['roi_xyxy_full_frame']
    restored = np.asarray(Image.fromarray(mask).resize((x1 - x0, y1 - y0), Image.Resampling.NEAREST))
    full_width, full_height = mapping['original_size']
    result = np.zeros((full_height, full_width), bool)
    result[y0:y1, x0:x1] = restored
    return result


def measured_crop_points(world, crop_mask, mapping):
    """Index the saved public XYZ without fabricating new depth samples."""
    world = np.asarray(world)
    full_mask = crop_mask_to_full(crop_mask, mapping)
    if world.shape != (*full_mask.shape, 3):
        raise ValueError('original world map and original RGB pixels differ')
    valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    return world[full_mask & valid], full_mask
