"""A typed stove RGB-D endpoint must survive legacy articulation settings."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


@pytest.mark.parametrize('mode', ['turn_on', 'turn_off'])
@pytest.mark.parametrize('verified', [True, False, None])
def test_stove_endpoint_does_not_get_overwritten_by_legacy_articulation(mode, verified, monkeypatch):
    from robots.libero import v5_verification

    stove = Entity('e1', 'stove', (0., 0., .92), (-.1, -.1, .90), (.1, .1, .94))
    primitives = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.08,
                                  env=SimpleNamespace(terminated=False, truncated=False))
    scene = SimpleNamespace(entities={stove.id: stove}, fixture_handle_geometry_v3=False,
                            fixture_front_geometry_v1=False,
                            view_axes=((1., 0., 0.), (0., 1., 0.)))
    executor = V5Executor(SimpleNamespace(primitives=primitives), scene,
        measured_action_receipts_v1=True, stove_rgbd_verification_v1=True,
        articulate_verification_v1=True)
    executor.measure_stove = lambda parent: {'state': 'on', 'entity': parent.id, 'source_step': 1}
    evidence = {'state': 'on' if mode == 'turn_on' else 'off_visual_transition',
                'verification_rule': 'measured_stove_rgbd/3-visual-transition-dev'}
    executor.verify_stove = lambda *args: (verified, evidence)
    executor._refresh = lambda names: None
    executor.vla_act = lambda *args: {'executed': True, 'chunks': 8}

    def reject_legacy(*args):
        raise AssertionError('generic positional articulation cannot override a stove endpoint')
    monkeypatch.setattr(v5_verification, 'measured_articulation', reject_legacy)
    receipt = {}
    executor._execute(Candidate('articulate', stove.id, mode=mode), receipt, None)
    assert receipt['articulate_verified'] is verified
    assert receipt['articulation_state'] == evidence
    assert receipt['verification'] == ('unmeasured' if verified is None else
                                       'verified' if verified else 'failed')


def test_legacy_articulation_still_runs_when_stove_rgbd_is_disabled(monkeypatch):
    from robots.libero import v5_verification

    stove = Entity('e1', 'stove', (0., 0., .92), (-.1, -.1, .90), (.1, .1, .94))
    primitives = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.08,
                                  env=SimpleNamespace(terminated=False, truncated=False))
    scene = SimpleNamespace(entities={stove.id: stove}, fixture_handle_geometry_v3=False,
                            fixture_front_geometry_v1=False,
                            view_axes=((1., 0., 0.), (0., 1., 0.)))
    executor = V5Executor(SimpleNamespace(primitives=primitives), scene,
        measured_action_receipts_v1=True, stove_rgbd_verification_v1=False,
        articulate_verification_v1=True)
    calls = []
    monkeypatch.setattr(v5_verification, 'measured_articulation',
        lambda *args: calls.append(args) or (False, {'reason': 'no_measured_positional_change'}))
    executor._refresh = lambda names: None
    executor.vla_act = lambda *args: {'executed': True, 'chunks': 8}
    receipt = {}
    executor._execute(Candidate('articulate', stove.id, mode='turn_on'), receipt, None)
    assert len(calls) == 1 and receipt['articulate_verified'] is False
