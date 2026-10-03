"""The explicit loaded OSC scale converts desired rotation to normalized input."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.tools import LiberoPrimitives
from robots.libero.v5_branch_state import controller_contract


def test_private_contract_reads_loaded_controller_without_stepping():
    controller = SimpleNamespace(input_max=np.ones(6), output_max=np.array([.05]*3+[.5]*3), input_ref_frame='base')
    wrapper = SimpleNamespace(env=SimpleNamespace(robots=[SimpleNamespace(controller=controller)]))
    result = controller_contract(wrapper)
    assert result['scope'] == 'private_actuator_diagnostic_only'
    assert result['robots'][0]['controller']['input_ref_frame'] == 'base'
    np.testing.assert_allclose(result['robots'][0]['controller']['output_max'][3:], .5)


@pytest.mark.parametrize('scale, expected', [(None, .8), (.5, .16)])
def test_pose_uses_explicit_scale_and_keeps_default_behavior(scale, expected):
    primitive = LiberoPrimitives.__new__(LiberoPrimitives)
    primitive._last_obs_eef_pos = np.zeros(3)
    primitive.env = SimpleNamespace(raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.]}, terminated=False, truncated=False)
    actions = []
    primitive._step_env = lambda action: actions.append(action.copy())
    options = {} if scale is None else {'rotation_action_scale': scale}
    primitive.move_pose([0., 0., 0.], target_pitch=.08, max_steps=1, **options)
    assert len(actions) == 1
    assert actions[0][3] == pytest.approx(expected)
