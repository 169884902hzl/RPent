"""Exercise scripted pose feedback with the installed Panda OSC action scale."""
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.tools import LiberoPrimitives
from robots.libero.v5_geometric_grasp import servo_grasp_pose


class PandaOSCFeedback:
    """Ideal feedback isolates command conversion from robot tracking errors."""

    def __init__(self, rotation):
        self._last_obs_eef_pos = np.array([0., 0., 1.])
        self.rotation = rotation
        self.actions = []
        self.env = SimpleNamespace(terminated=False, truncated=False,
            raw_obs=lambda: {'robot0_eef_quat': self.rotation.as_quat()})

    def _step_env(self, action):
        self.actions.append(action.copy())
        self._last_obs_eef_pos += action[:3] * .05
        self.rotation = Rotation.from_rotvec(action[3:6] * .50) * self.rotation


def test_move_pose_matches_panda_scale_and_converges_without_yaw_oscillation():
    primitive = PandaOSCFeedback(Rotation.from_euler('z', .2) * Rotation.from_euler('x', np.pi))
    result = LiberoPrimitives.move_pose(primitive, [0., 0., 1.],
        target_pitch=0., target_yaw=0., max_steps=20, trace_steps=True)
    assert abs(float(primitive.actions[0][5]) * .5) <= .080001
    assert result['actions_used'] < 20
    assert abs(result['final_yaw_err']) < .05


def test_full_pose_matches_panda_scale_and_converges_without_rotation_oscillation():
    primitive = PandaOSCFeedback(Rotation.from_euler('x', .2))
    result = servo_grasp_pose(primitive, [0., 0., 1.], Rotation.identity().as_quat(),
        max_steps=20, trace_steps=True)
    assert np.linalg.norm(primitive.actions[0][3:6] * .5) <= .080001
    assert result['actions_used'] < 20
    assert result['final_orientation_err_rad'] < .05


def test_explicit_legacy_scale_preserves_the_reproducible_conversion_mismatch():
    primitive = PandaOSCFeedback(Rotation.from_euler('z', .2) * Rotation.from_euler('x', np.pi))
    result = LiberoPrimitives.move_pose(primitive, [0., 0., 1.],
        target_pitch=0., target_yaw=0., rotation_action_scale=.10, max_steps=20)
    assert result['steps_used'] == 20
    assert abs(result['final_yaw_err']) > .05
