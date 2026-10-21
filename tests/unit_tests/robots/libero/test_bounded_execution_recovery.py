"""Regress the real N1 zero-step receipt and support-contact failures."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_chunk import check_receipt
from robots.libero.bounded_screen import PublicRouteScreen
from rpent.skill_package.progress import PublicProgress

FIXTURE=json.loads((Path(__file__).parent/'fixtures/execution_zero_step_receipts_20261022.json').read_bytes())


def test_real_zero_step_lifts_do_not_claim_grasp_failure():
    rows=[r for r in FIXTURE['cases'] if r['receipt']['skill']=='lift']
    assert rows
    for row in rows:
        receipt=copy.deepcopy(row['receipt'])
        assert receipt['steps_used']==0
        conditions=[c['condition'] for c in receipt['expectation_checks']]
        assert any(c['metric']=='held' for c in conditions)
        check_receipt({'expected_receipt':conditions},receipt,{})
        assert all(c['measured'] is None and c['passed'] is None for c in receipt['expectation_checks'])


def test_real_container_support_pair_can_separate_without_pair_identity_lock():
    rows=[r for r in FIXTURE['cases'] if r['case'] in (1,7) and r['reason']=='measured_payload_collision']
    assert len(rows)==2
    for row in rows:
        diagnostic=row['screen']
        point=np.array(diagnostic['payload_point'])
        obstacle=np.array(diagnostic['obstacle_point'])
        assert np.linalg.norm(point-obstacle)<.004
        # Exact recorded target/obstacle coordinates. A second measured-depth
        # sample represents the same support; outgoing motion changes nearest
        # sample identity. Hand hull is far away from this support contact.
        pose={'xyz_m':[0.,0.,1.], 'quat_xyzw':[0.,0.,0.,1.]}
        payload=np.array([point,point+[.002,0.,0.]])-pose['xyz_m']
        geometry={'boxes':[{'name':'palm','lower':[-.005]*3,'upper':[.005]*3}]}
        screen=PublicRouteScreen([obstacle,obstacle+[.002,0.,0.]],geometry,
            SimpleNamespace(check=lambda *a:{'solution_found':True}),payload_local=payload,initial_pose=pose)
        screen.support_separation=True
        assert screen([pose,{**pose,'xyz_m':[.001,0.,1.01]}])['passed']


def test_box_surface_minimum_allows_new_pixels_but_rejects_deeper_incursion():
    geometry={'boxes':[{'name':'finger','lower':[-.01]*3,'upper':[.01]*3}]}
    pose={'xyz_m':[0.,0.,1.], 'quat_xyzw':[0.,0.,0.,1.]}
    # Rotated about z by -90 inside the screen; this horizontal plane remains
    # at the same occupied shell clearance as different points pass the hull.
    points=np.array([[x,.012,1.] for x in np.arange(-.03,.031,.002)])
    screen=PublicRouteScreen(points,geometry,SimpleNamespace(check=lambda *a:{'solution_found':True}),initial_pose=pose)
    assert screen([pose,{**pose,'xyz_m':[.02,0.,1.]}])['passed']
    assert not screen([pose,{**pose,'xyz_m':[0.,.001,1.]}])['passed']


def test_planner_only_rejection_does_not_consume_public_stagnation():
    p=PublicProgress(11)
    p.update({'revision':0},[])
    candidate={'id':'a','skill':'move_to','parameters':{'anchor_id':'measured'}}
    p.record_actions([candidate],[{'candidate_id':'a','steps_used':0,'phase':'planning_unreachable'}])
    p.update({'revision':1},[])
    assert p.stagnant==0 and not p.action_groups
