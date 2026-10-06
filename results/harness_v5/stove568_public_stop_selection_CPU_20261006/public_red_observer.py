"""Public-only red observation; unavailable endpoint calibration never stops."""

from io import BytesIO


def stop_decision(public_views, calibration):
    """Require an admitted public endpoint, never use a diagnostic label."""
    if calibration.get("endpoint_stop_admitted") is not True:
        return {"stop": False, "reason": "public_off_endpoint_unmeasured",
                "calibration_admitted": False}
    threshold = calibration.get("red_fraction_threshold")
    if threshold is None:
        raise ValueError("admitted endpoint requires an explicit public threshold")
    available = [v for v in public_views.values() if v.get("surface_pixels", 0) >= 100
                 and v.get("red_fraction") is not None]
    stop = bool(available) and all(v["red_fraction"] <= threshold for v in available)
    return {"stop": stop, "reason": "admitted_public_red_endpoint" if stop else "public_endpoint_not_observed",
            "calibration_admitted": True, "available_views": len(available)}


def observe(executor, cached_shell, calibration):
    """Measure current two-view RGB-D inside cached static measured bounds."""
    import numpy as np
    from PIL import Image
    from robots.libero.v5_stove_measurement import measure_stove_rgbd
    from scripts.probe_v5_stove521_endpoint import identity

    executor.capture()
    state, views = executor.toolkit._state, {}
    step = state.latest_step
    for camera in ("agentview", "wrist"):
        if cached_shell is None:
            views[camera] = {"surface_pixels": 0, "red_fraction": None,
                             "reason": "no_initial_public_stove_bound"}
            continue
        image_bytes = state.load_bytes(camera + "_high.png", step=step)
        image = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
        world = state.load(camera + "_world_high.npz", step=step)
        packet = measure_stove_rgbd(image, world, cached_shell, step, camera)
        views[camera] = {**packet["features"], "version": packet["version"],
                        "state": packet["state"], "reason": packet["reason"],
                        "raw_rgb": identity(state.artifact_path(camera + "_high.png", step=step)),
                        "raw_world": identity(state.artifact_path(camera + "_world_high.npz", step=step))}
    return {"source_step": step, "views": views, "stop_decision": stop_decision(views, calibration),
            "coordinate_source": "current_rgbd_with_cached_measured_static_fixture_bounds",
            "cached_bound_source_step": cached_shell.source_step if cached_shell is not None else None,
            "cached_entity_visibility_is_not_current_visibility_evidence": True,
            "private_labels_in_observer": False}
