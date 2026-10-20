"""A selected arm route rejects new intrusion and permits a measured escape."""
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_arm_screen import screen_arm_route


def test_arm_exact_fallback_checks_between_endpoint_joint_solutions(monkeypatch):
    import robots.libero.bounded_arm_screen as arm
    hull = {'name':'link','node':0,'lower':np.full(3,-.005),'upper':np.full(3,.005),
        'equations':np.array([[1,0,0,-.005],[-1,0,0,-.005],[0,1,0,-.005],
            [0,-1,0,-.005],[0,0,1,-.005],[0,0,-1,-.005]])}
    def forward(q,links=False):
        poses = np.repeat(np.eye(4)[None],len(q),axis=0)
        poses[:,0,3] = q[:,0]
        return poses[:,:3,3],None,None,[poses]
    kernel = SimpleNamespace(forward=forward)
    monkeypatch.setattr(arm.BatchedDampedIK,'from_source',lambda *_:kernel)
    monkeypatch.setattr(arm,'robot_link_hulls',lambda *_:[hull])
    monkeypatch.setattr(arm,'capture_fields',lambda *_:SimpleNamespace(get=lambda *_:
        SimpleNamespace(covers=lambda *_:False)))
    monkeypatch.setattr(arm,'link_distance_query',lambda field,ik,q,h:
        {'per_link':[{'strictly_clear_of_observed_cloud':[False]*len(q)}]})
    fixed = np.eye(4);fixed[0,3] = 1.
    screen = SimpleNamespace(ik=SimpleNamespace(joints=np.zeros(7),nodes=[(fixed,None)],
        reference={'path':'static_robot.xml'}),points=np.array([[.008,0.,0.]]),
        target=np.empty((0,3)),capture_points=None,capture_key=None,contact_axis=None)
    def checks(x):
        return [{'solves':[{'solution_found':True,'joint_positions_rad':[x,0,0,0,0,0,0]}]}]
    blocked = screen_arm_route(screen,checks(.03))
    assert not blocked['passed'] and blocked['reason']=='measured_arm_sweep_collision'
    assert blocked['joint_sample']>0 and blocked['arm_collisions_checked']
    assert screen_arm_route(screen,checks(-.03))['passed']
