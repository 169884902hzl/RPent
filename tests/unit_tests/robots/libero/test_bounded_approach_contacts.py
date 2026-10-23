"""Occupied-start correction and final target contact keep other obstacles strict."""
from types import SimpleNamespace
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_screen import PublicRouteScreen

Q = Rotation.from_euler('z',90,degrees=True).as_quat().tolist()

def pose(x=0.,z=1.):
    return {'xyz_m':[x,0.,z],'quat_xyzw':Q}

def repaired(points, *, target=(), geometry=None):
    geometry=geometry or {'boxes':[{'name':'palm','lower':[-.01]*3,'upper':[.01]*3}]}
    ik=SimpleNamespace(check=lambda *_:{'solution_found':True})
    source=PublicRouteScreen(points,geometry,ik,contact_points=target,initial_pose=pose())
    return source.with_approach_contact_rules([10.,0.,2.],[10.,0.,1.])

def test_positive_occupied_margin_is_not_physical_penetration_but_new_contact_is_rejected():
    screen=repaired([[0.,0.,1.012]])
    assert screen([pose(),pose(z=1.001)])['passed']
    result=screen([pose(),pose(z=1.003)])
    assert not result['passed'] and result['clearance_threshold_m']==.004

def test_existing_penetration_may_separate_but_must_not_deepen():
    screen=repaired([[0.,0.,1.009]])
    assert screen([pose(),pose(z=.999)])['passed']
    assert not screen([pose(),pose(z=1.001)])['passed']

def test_start_allowance_does_not_exempt_a_new_obstacle_in_the_same_hand_box():
    screen=repaired([[0.,0.,1.012],[.1,0.,1.012]])
    result=screen([pose(),pose(x=.1)])
    assert not result['passed'] and result['counts']['palm']

def test_final_segment_allows_target_fingers_but_retains_palm_and_other_objects():
    geometry={'boxes':[{'name':'palm','lower':[-.01]*3,'upper':[.01]*3},
        {'name':'leftfinger','lower':[.02,-.01,-.01],'upper':[.03,.01,.01]}]}
    source=repaired([[2.,2.,2.]],target=[[.025,0.,.9]],geometry=geometry)
    stage=source.with_approach_contact_rules([0.,0.,1.1],[0.,0.,.9])
    assert not source([pose(z=.9)])['passed']
    assert stage([pose(z=1.1),pose(z=.9)])['passed']
    assert not stage([pose(x=.001,z=.9)])['passed']
    other=repaired([[.025,0.,.9]],target=[[.025,0.,.9]],geometry=geometry).with_approach_contact_rules([0.,0.,1.1],[0.,0.,.9])
    assert not other([pose(z=.9)])['passed']
    palm=repaired([[2.,2.,2.]],target=[[0.,0.,.9]],geometry=geometry).with_approach_contact_rules([0.,0.,1.1],[0.,0.,.9])
    assert not palm([pose(z=.9)])['passed']
