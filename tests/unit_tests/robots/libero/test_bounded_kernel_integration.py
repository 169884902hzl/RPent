"""Kernel acceleration preserves exact public route results and checkpointability."""
import copy
import pickle
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_screen import PublicRouteScreen


def reachable(*args):
    return {'solution_found':True}


def test_voxel_fast_clear_retains_exact_complete_route_result():
    plane = np.array([[x,y,.8] for x in np.linspace(-.5,.5,40) for y in np.linspace(-.5,.5,40)])
    geometry = {'boxes':[{'name':'palm','lower':[-.01]*3,'upper':[.01]*3}]}
    payload = [[0.,0.,0.]]
    screen = PublicRouteScreen(plane,geometry,SimpleNamespace(check=reachable),payload_local=payload)
    route = [{'xyz_m':[x,0.,1.],'quat_xyzw':[0.,0.,0.,1.]} for x in (0.,.1)]
    expected = screen(route)
    fast = PublicRouteScreen(plane,geometry,SimpleNamespace(check=reachable),
        use_kernel=True,capture_points=plane,payload_local=payload)
    actual = fast(route)
    assert actual == expected
    assert fast._geometry_kernel.stats['fast_accept']>0
    restored = pickle.loads(pickle.dumps(fast))
    assert '_geometry_kernel' not in vars(restored)
    assert restored(route)==expected


def test_voxel_unknown_or_near_obstacle_uses_exact_collision_check():
    geometry = {'boxes':[{'name':'palm','lower':[-.01]*3,'upper':[.01]*3}]}
    points = [[.06,0.,1.]]
    route = [{'xyz_m':[x,0.,1.],'quat_xyzw':[0.,0.,0.,1.]} for x in (0.,.1)]
    original = PublicRouteScreen(points,geometry,SimpleNamespace(check=reachable))
    fast = PublicRouteScreen(points,geometry,SimpleNamespace(check=reachable),use_kernel=True)
    assert fast(route)==original(route)
    assert '_geometry_kernel' not in vars(fast)
