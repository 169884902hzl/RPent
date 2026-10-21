"""A blocked upward hold probe may use one other screened bounded direction."""
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_skills import MeasuredSkillAdapter


def probe(monkeypatch, *, all_blocked=False):
    import robots.libero.bounded_skills as skills
    robot = {'eef_xyz_m': [.1, .2, .5]}
    monkeypatch.setattr(skills, 'measured_robot', lambda _: robot)
    checked, executed = [], []

    class Motion:
        def __init__(self, *args):
            pass

        def prepare(self, route):
            delta = np.asarray(route[0]['xyz_m'])-robot['eef_xyz_m']
            checked.append(delta)
            return None, None, None, {'passed': not all_blocked and abs(delta[2]) < 1e-10,
                                      'reason': 'measured_payload_collision'}

        def run(self, route, **kwargs):
            executed.append(route)
            return {'executed': True, 'steps_used': 12, 'stop_reason': 'endpoint'}

    monkeypatch.setattr(skills, 'SmoothMotion', Motion)
    adapter = SimpleNamespace(p=object(), config=object(), gripper_command=1.)
    return adapter, checked, executed


def test_blocked_upward_probe_executes_one_screened_lateral_motion(monkeypatch):
    adapter, checked, executed = probe(monkeypatch)
    result = MeasuredSkillAdapter._hold_verification_motion(adapter, object(), .047)
    assert len(executed) == 1
    assert len(checked) == 2 and checked[0][2] > 0
    assert abs(np.linalg.norm(result['verification_offset_m'])-.01) < 1e-12
    assert result['verification_offset_m'][2] == 0
    assert result['steps_used'] == 12


def test_all_blocked_routes_do_not_move_or_lower_below_required_rise(monkeypatch):
    adapter, checked, executed = probe(monkeypatch, all_blocked=True)
    result = MeasuredSkillAdapter._hold_verification_motion(adapter, object(), .035)
    assert not executed and result['steps_used'] == 0
    assert all(.035+delta[2] >= .03 for delta in checked)
    assert result['stop_reason'] == 'no_screened_verification_route'
