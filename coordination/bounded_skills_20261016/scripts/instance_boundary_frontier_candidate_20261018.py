import numpy as np

def complete_instance_boundary(world, mask, *, rounds=3, max_step_m=.003,
                               max_extrapolation_error_m=.001, measured_tangent_spacing=False):
    """Recover a narrow omitted rim only along a measured continuous surface.

    Each added pixel needs two consecutive interior pixels and must agree
    with their 3-D linear extrapolation. A depth jump to a table or neighbour
    is retained as scene geometry. This is image-space instance refinement,
    not a nearest-neighbour carve of the collision cloud. With measured
    tangent spacing, a grazing surface may have larger per-pixel spacing;
    its next step must agree with the two measured interior samples within
    the same extrapolation error. Callers must independently retain static
    scene membership when using this option for moving payloads.
    """
    world, mask = np.asarray(world), np.asarray(mask, dtype=bool)
    valid = np.isfinite(world).all(axis=2) & (np.linalg.norm(world, axis=2) > 1e-6)
    current = mask & valid
    added = []
    frontier = None
    for _ in range(rounds):
        extended = np.zeros(mask.shape, dtype=bool)
        for dy, dx in ((0,1), (0,-1), (1,0), (-1,0)):
            if frontier is None:
                y0, y1 = max(0, 2*dy), mask.shape[0]+min(0, 2*dy)
                x0, x1 = max(0, 2*dx), mask.shape[1]+min(0, 2*dx)
                a = (slice(y0, y1), slice(x0, x1))
                b = (slice(y0-dy, y1-dy), slice(x0-dx, x1-dx))
                c = (slice(y0-2*dy, y1-2*dy), slice(x0-2*dx, x1-2*dx))
                ys, xs = np.nonzero(valid[a] & ~current[a] & current[b] & current[c])
                ys, xs = ys+y0, xs+x0
            else:
                # Eligibility can only change next to one of the two
                # newly interior pixels; failed old tests stay false.
                fy, fx = frontier
                ys, xs = np.r_[fy+dy, fy+2*dy], np.r_[fx+dx, fx+2*dx]
                inside = ((ys >= max(0, 2*dy)) & (ys < mask.shape[0]+min(0, 2*dy))
                    & (xs >= max(0, 2*dx)) & (xs < mask.shape[1]+min(0, 2*dx)))
                ids = np.unique(ys[inside]*mask.shape[1]+xs[inside])
                ys, xs = np.divmod(ids, mask.shape[1])
                eligible = (valid[ys, xs] & ~current[ys, xs]
                    & current[ys-dy, xs-dx] & current[ys-2*dy, xs-2*dx])
                ys, xs = ys[eligible], xs[eligible]
            if not len(ys):
                continue
            candidate, near, inner = world[ys, xs], world[ys-dy, xs-dx], world[ys-2*dy, xs-2*dx]
            step = near-inner
            continuous = np.linalg.norm(candidate-(near+step),axis=1) <= max_extrapolation_error_m
            if not measured_tangent_spacing:
                continuous &= ((np.linalg.norm(step,axis=1) <= max_step_m)
                               & (np.linalg.norm(candidate-near,axis=1) <= max_step_m))
            extended[ys, xs] |= continuous
        added.append(int(extended.sum()))
        current |= extended
        frontier = np.nonzero(extended)
        if not extended.any():
            break
    return current, {'version':'public-depth-continuous-instance-boundary/1-dev',
        'source':'current_instance_mask_and_same_view_rgbd',
        'input_pixels':int(np.count_nonzero(mask)), 'added_pixels_per_round':added,
        'rounds':rounds, 'max_step_m':None if measured_tangent_spacing else max_step_m,
        'spacing_source': 'measured_two_pixel_tangent' if measured_tangent_spacing else 'fixed_metric_limit',
        'max_extrapolation_error_m':max_extrapolation_error_m,
        'private_target_pose_used':False}
