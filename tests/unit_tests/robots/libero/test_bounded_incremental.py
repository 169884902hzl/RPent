"""Incremental refresh follows executed public motion, including held geometry."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_incremental import refresh_names, swept_bounds
from robots.libero.bounded_motion import measured_robot, public_control
from robots.libero.v5_state import Entity
from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives


def adapter():
    p = FakePrimitives()
    p._bounded_perception_sweep = []
    entities = {
        'near': Entity('near', 'cup', (.1, 0., 1.), (.08, -.02, .98), (.12, .02, 1.02)),
        'far': Entity('far', 'box', (.1, .2, 1.), (.08, .18, .98), (.12, .22, 1.02)),
    }
    return SimpleNamespace(p=p, ex=SimpleNamespace(toolkit=SimpleNamespace(
        _state=SimpleNamespace(latest_step=1))), held=None, payload_reference=None,
        _incremental_touched=set(), _incremental_route=[],
        _incremental_previous_robot=measured_robot(p),
        geometry={'boxes': [{'lower': [-.02, -.01, -.01], 'upper': [.02, .01, .01]}]},
        scene=SimpleNamespace(entities=entities, view_axes=((1, 0, 0), (0, -1, 0))))


def test_rejected_planned_route_does_not_refresh_untouched_anchors():
    a = adapter()
    a._incremental_route = [[0., 0., 1.], [.1, .2, 1.]]
    assert refresh_names(a, ['cup', 'box']) == []
    assert not a._incremental_route


def test_executed_sweep_refreshes_nearby_anchor_but_keeps_distant_cache():
    a = adapter()
    for _ in range(4):
        public_control(a.p, np.array([.5, 0., 0., 0., 0., 0., -1.]))
    assert refresh_names(a, ['cup', 'box']) == ['cup']
    assert not a.p._bounded_perception_sweep
    assert len(a.p._bounded_motion_samples) <= 4
    assert refresh_names(a, ['cup', 'box']) == []


def test_untracked_external_motion_forces_refresh_and_first_capture_consumes_history():
    a = adapter()
    a.p.env.position += [.2, 0., 0.]
    assert refresh_names(a, ['cup', 'box']) == ['box', 'cup']
    assert all('untracked_robot_motion' in r['reasons'] for r in a.incremental_evidence)
    public_control(a.p, np.zeros(7))
    a._incremental_previous_robot = None
    assert refresh_names(a, ['cup', 'box']) == ['cup', 'box']
    assert not a.p._bounded_perception_sweep


def test_payload_sweep_and_release_settling_do_not_use_only_empty_hand_geometry():
    a = adapter()
    a.held = 'held'
    robot = measured_robot(a.p)
    a.payload_reference = {'robot': robot, 'target': [[0., .2, 1.], [.01, .21, 1.01]]}
    for _ in range(4):
        public_control(a.p, np.array([.5, 0., 0., 0., 0., 0., 1.]))
    assert refresh_names(a, ['cup', 'box']) == ['box', 'cup']
    a.held = None
    a.payload_reference = None
    a._incremental_released_payload = True
    assert refresh_names(a, ['cup', 'box']) == ['box', 'cup']
    assert all('released_payload_settling' in r['reasons'] for r in a.incremental_evidence)


def test_rotating_hand_envelope_contains_intermediate_mesh_corner():
    before = measured_robot(FakePrimitives())
    after = deepcopy(before)
    after['eef_quat_xyzw'] = Rotation.from_euler('z', 90, degrees=True).as_quat().tolist()
    geometry = {'boxes': [{'lower': [.09, -.002, -.002], 'upper': [.1, .002, .002]}]}
    lo, hi = swept_bounds(geometry, [{'before': before, 'after': after}], margin_m=0.)
    for angle in np.linspace(0., 90., 31):
        point = Rotation.from_euler('z', angle, degrees=True).apply([.1, 0., 0.])+before['eef_xyz_m']
        assert ((lo <= point) & (point <= hi)).all()


def test_newly_seen_support_is_not_reported_as_a_moved_support():
    a = adapter()
    a.scene.entities['support'] = Entity('support', 'surface', (.1, 0., .961),
        (0., -.1, .95), (.2, .1, .961))
    a._last_scene_changes = {'support'}
    assert refresh_names(a, ['cup']) == []
    a._incremental_support_changes = {'support'}
    assert refresh_names(a, ['cup']) == ['cup']
    assert 'support_moved_or_contacted' in a.incremental_evidence[0]['reasons']
