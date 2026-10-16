"""Measured target contact remains separate from scene obstacles."""
from types import SimpleNamespace
import numpy as np
from robots.libero.bounded_screen import PublicRouteScreen


def test_target_broad_phase_keeps_real_collisions_and_allowed_finger_contact():
    geometry = {"boxes": [
        {"name": "palm", "lower": [-.02, -.02, .04], "upper": [.02, .02, .06]},
        {"name": "left_pad", "lower": [-.02, -.02, -.01], "upper": [.02, .02, .01]}]}
    ik = SimpleNamespace(check=lambda xyz, quat: {"solution_found": True})
    # Large distant mask must not hide the one pixel that intersects a pad.
    target = np.r_[np.full((10000, 3), 10.), [[0., 0., 0.]]]
    scene = np.array([[1., 1., 1.]])
    pose = [{"xyz_m": [0., 0., 0.], "quat_xyzw": [0., 0., 0., 1.]}]
    blocked = PublicRouteScreen(scene, geometry, ik, contact_points=target)(pose)
    allowed = PublicRouteScreen(scene, geometry, ik, contact_points=target, contact_allowed=True)(pose)
    assert blocked["reason"] == "measured_sweep_collision"
    assert blocked["target_counts"]["left_pad"] == 1
    assert allowed["passed"]
    obstacle = PublicRouteScreen(np.array([[0., 0., 0.]]), geometry, ik,
        contact_points=target, contact_allowed=True)(pose)
    assert obstacle["collision"] and obstacle["counts"]["left_pad"] == 1
