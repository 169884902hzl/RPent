"""Regress the real N1 zero-step receipt and support-contact failures."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from robots.libero.bounded_chunk import check_receipt
from robots.libero.bounded_screen import PublicRouteScreen
from rpent.skill_package.progress import PublicProgress
from tests.unit_tests.robots.libero.test_bounded_skills import adapter as adapter
from tests.unit_tests.robots.libero.test_bounded_skills import decision

FIXTURE=json.loads((Path(__file__).parent/'fixtures/execution_zero_step_receipts_20261022.json').read_bytes())


def test_object_ingress_does_not_require_a_pregrasp_payload(adapter, monkeypatch):
    """Regress bowl s0's accepted ingress before its speculative lift reject."""
    from dataclasses import replace

    endpoint = {
        'xyz_m': [-.05939897020450896, .25219549349060766, .9421273639186665],
        'quat_xyzw': [.9937001961305982, -.11207104983005521, 0., 0.],
    }
    entry = {**endpoint, 'xyz_m': [*endpoint['xyz_m'][:2], endpoint['xyz_m'][2]+.15]}
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='bowl', part_of=None)
    adapter.plans['e1'] = {**endpoint, 'width_m': .00571145941005056}
    geometry = {'boxes': [{'name': 'palm', 'lower': [.2]*3, 'upper': [.21]*3}]}
    screen = PublicRouteScreen(
        [[-.02981247752904892, .23530204594135284, .9400051832199097]],
        geometry, SimpleNamespace(last_solution=None, check=lambda *_: {'solution_found': True}),
        contact_points=[[-.03008072264492511, .2352297455072403, .9407573676109313]],
        contact_allowed=True)
    monkeypatch.setattr(adapter, '_cloud_and_ik', lambda *_args, **_kwargs: screen)
    # No closed hand or attachment has been measured at this approach.
    # The actual descend/lift remain screened when those skills execute.
    monkeypatch.setattr('robots.libero.bounded_skills.gripper_at_measured_fingers',
        lambda *_args: pytest.fail('pre-grasp approach assumed a future closure'))
    assert screen([entry, endpoint])['passed']
    result = adapter._screen_contact_sequence('e1', entry, approach='above')
    assert result['passed'] and 'contact_sequence_stage' not in result


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


def test_recorded_support_separation_uses_surface_not_nearest_pixel():
    row=next(r for r in FIXTURE['cases'] if r['case']==1 and r['reason']=='measured_payload_collision')
    point=np.asarray(row['screen']['payload_point'])
    obstacle=np.asarray(row['screen']['obstacle_point'])
    pose={'xyz_m':[0.,0.,1.], 'quat_xyzw':[0.,0.,0.,1.]}
    # The new physical replay rejected a sub-micrometre clearance decrease
    # at sample 2. Sampled Euclidean distances have tangential pixel error;
    # signed height above this observed plane increases throughout the lift.
    plane=np.array([obstacle+[x,y,0.] for x in np.arange(-.02,.021,.004)
        for y in np.arange(-.02,.021,.004)])
    geometry={'boxes':[{'name':'palm','lower':[-.005]*3,'upper':[.005]*3}]}
    screen=PublicRouteScreen(plane,geometry,SimpleNamespace(check=lambda *a:{'solution_found':True}),
        payload_local=[point-np.asarray(pose['xyz_m'])],initial_pose=pose)
    screen.support_separation=True
    shift=np.array([0.,5e-6,1e-7])
    assert np.linalg.norm(point+shift-obstacle)<np.linalg.norm(point-obstacle)
    up={**pose,'xyz_m':(np.asarray(pose['xyz_m'])+shift).tolist()}
    result=screen([pose,up,{**pose,'xyz_m':[0.,5e-6,1.01]}])
    assert result['passed'],result
    assert len(screen._support_planes())==1
    # Returning to the already occupied start is not a new incursion. The
    # removed temporal-monotonic check rejected this harmless return.
    assert screen([pose,up,pose])['passed']
    assert not screen([pose,{**pose,'xyz_m':[0.,0.,.998]}])['passed']


def test_planner_only_rejection_does_not_consume_public_stagnation():
    p=PublicProgress(11)
    p.update({'revision':0},[])
    candidate={'id':'a','skill':'move_to','parameters':{'anchor_id':'measured'}}
    p.record_actions([candidate],[{'candidate_id':'a','steps_used':0,'phase':'planning_unreachable'}])
    p.update({'revision':1},[])
    assert p.stagnant==0 and not p.action_groups


@pytest.mark.parametrize('name,opening,retained',[
    ('box',.036835659236338025,True),('box',.001,False),
    ('box',.08,False),('microwave',.036835659236338025,False)])
def test_scan_preserves_nonempty_pending_object_grasp_without_claiming_hold(adapter,name,opening,retained):
    from dataclasses import replace

    request=adapter.request(k=1)
    source=replace(adapter.scene.entities['e1'],name=name)
    adapter.scene.entities['e1']=source
    adapter.scene.vocabulary={name}
    adapter.active='e1'
    adapter.grasp_reference=(source,adapter.robot())
    adapter.gripper_command=1.
    raw=adapter.p.env.raw_obs
    adapter.p.env.raw_obs=lambda:{**raw(),'robot0_gripper_qpos':[opening/2,-opening/2]}
    # Use the same 36.8 mm aperture as the real rejected container lift.
    scan=next(c for c in request['candidates'] if c['skill']=='observe'
        and c['parameters']['mode']=='wrist_scan')
    receipt,=adapter.execute(request,decision(request,[scan['id']]))
    assert receipt['steps_used']>0
    assert (adapter.active=='e1') is retained
    assert (adapter.grasp_reference is not None) is retained
    assert adapter.held is None
    assert all(change['held'] is None for change in receipt['changes'])
