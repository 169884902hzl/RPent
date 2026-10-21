"""Already executed policy motion can verify a hold without another movement."""
import copy

import numpy as np

from robots.libero.bounded_vla_hold import measured_block_hold
from tests.unit_tests.robots.libero.test_bounded_skills import adapter  # noqa: F401


def pair():
    import cv2

    rng = np.random.default_rng(63)
    image = cv2.GaussianBlur(rng.integers(0, 256, (128, 128, 3), dtype=np.uint8), (5, 5), 0)
    y, x = np.mgrid[:128, :128]
    world = np.stack([x*.001, y*.001, np.ones_like(x)], axis=-1)
    earlier = {'sim_step': 3, 'robot': {'eef_xyz_m': [0., 0., 1.], 'gripper_opening_m': .01},
               'views': {'agentview': {'rgb': image, 'world': world}}}
    current = copy.deepcopy(earlier)
    current['sim_step'] = 13
    current['robot']['eef_xyz_m'] = [.01, 0., 1.]
    current['views']['agentview']['rgb'] = cv2.warpAffine(image,
        np.array([[1., 0., 10.], [0., 1., 0.]]), (128, 128))
    target = world[(x >= 40) & (x < 105) & (y >= 30) & (y < 95)]
    return earlier, current, target


def aperture(value):
    return .005 < value < .075, {'source': 'test_calibration'}


def test_public_block_motion_establishes_coupling_and_keeps_input_frames():
    earlier, current, target = pair()
    proof, frames = measured_block_hold([earlier], current, target, aperture)
    assert proof['new_control_steps'] == 0 and proof['private_truth_used'] is False
    assert proof['relative_displacement_m'] < .001
    assert proof['hand_displacement_m'] == .01
    assert frames['earlier'] is earlier and frames['current'] is current


def test_stationary_object_with_moving_hand_does_not_establish_a_hold():
    earlier, current, target = pair()
    current['views'] = earlier['views']
    current['robot']['eef_xyz_m'] = [.03, 0., 1.]
    assert measured_block_hold([earlier], current, target, aperture) == (None, None)


def test_open_jaws_do_not_verify_an_attached_object():
    earlier, current, target = pair()
    earlier['robot']['gripper_opening_m'] = .08
    assert measured_block_hold([earlier], current, target, aperture) == (None, None)


def test_missing_texture_retains_unmeasured_hold():
    earlier, current, target = pair()
    earlier['views']['agentview']['rgb'][:] = 0
    assert measured_block_hold([earlier], current, target, aperture) == (None, None)


def run_observation_reuse(adapter, monkeypatch, *, advance_after_capture):
    from tests.unit_tests.robots.libero.test_bounded_schema6 import enable

    enable(adapter)
    adapter.allow_vla = True
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'call_vla')
    original = adapter.refresh
    calls = []
    def refresh(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(adapter, 'refresh', refresh)
    def call(_):
        refresh()
        observed = {'capture_step': adapter.ex.toolkit._state.latest_step,
                    'used_sim_steps': adapter.p.env.execution_budget()['used_sim_steps']}
        if advance_after_capture:
            adapter.p._step_env(np.zeros(7))
        return {'outcome': 'failure', 'stop_reason': 'no_progress_blocks',
                'post_handoff_observation': observed}
    monkeypatch.setattr(adapter, 'call_vla', call)
    adapter._execute_one(request, candidate)
    return len(calls), adapter.details[-1]['execution']


def test_vla_final_observation_is_reused_without_intervening_physics(adapter, monkeypatch):
    calls, detail = run_observation_reuse(adapter, monkeypatch, advance_after_capture=False)
    assert calls == 1
    assert detail['reused_post_handoff_observation'] is True


def test_vla_final_observation_is_refreshed_after_another_control(adapter, monkeypatch):
    calls, detail = run_observation_reuse(adapter, monkeypatch, advance_after_capture=True)
    assert calls == 2
    assert 'reused_post_handoff_observation' not in detail
