# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Regressions for failure evidence, measured support and category card binding."""

import random
import json

import numpy as np

from robots.libero.v5_cards import VERSION, card_view, resolve_card, validate_card
from robots.libero.v5_fixture_parts import above_work_surface, fixture_parts, fixture_points
from robots.libero.v5_fixture_parts import measured_handle_front


def test_closed_cabinet_front_can_be_measured_from_repeated_handle_rows():
    parent = Entity("e1", "cabinet", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.2))
    handles = np.array([(x, .13 + d, z + h)
                        for x in np.linspace(-.06, .06, 12)
                        for d in (0, .003) for h in (-.006, .006)
                        for z in (.95, 1.04, 1.13)])
    axis, evidence, points = measured_handle_front(handles, parent)
    assert axis == (0., 1., 0.)
    assert evidence["basis"] == "current_rgbd_repeated_handle_rows/3-dev"
    assert len(points) == len(handles)


def test_one_nearby_rack_or_two_ambiguous_fronts_cannot_calibrate_drawer_axis():
    parent = Entity("e1", "cabinet", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.2))
    single = np.array([(x, .13, .99 + h) for x in np.linspace(-.06, .06, 40)
                       for h in (-.003, .003)])
    assert measured_handle_front(single, parent)[0] is None
    rows = np.concatenate([single, single + (0, 0, .1)])
    assert measured_handle_front(np.concatenate([rows, rows[:, [1, 0, 2]]]), parent)[0] is None
from robots.libero.v5_state import Candidate, Entity, candidates, recent_failures, serialize
from robots.libero.v5_verification import measured_articulation, strict_place_verified, vertical_face, measured_fixture_endpoint


def entity(eid="e1", name="bowl", z=.14):
    return Entity(eid, name, (0, 0, z), (-.01, -.01, z-.01), (.01, .01, z+.01))


def test_wrong_drawer_branch_is_unknown_while_generic_and_selected_drawer_labels_survive():
    from scripts.rerender_v5_format118_20261002 import legacy_fixture_overrides

    entities = [entity("e1", "cabinet top drawer"),
                entity("e2", "cabinet bottom drawer"), entity("e3", "cabinet")]
    tested = {"articulate(e1,open)", "articulate(e2,open)",
              "articulate(e3,open)", "finish()"}
    assert legacy_fixture_overrides(tested, entities, "open the lower drawer") == {"articulate(e1,open)"}
    assert legacy_fixture_overrides(tested, entities, "open the upper drawer") == {"articulate(e2,open)"}
    assert legacy_fixture_overrides(tested, entities, "put the bowl in the drawer") == set()


def test_failures_match_the_bound_action_and_verified_recovery_resets_count():
    action = Candidate("place", "e1", "e2", "on")
    failed = {"tool": "place", "object": "e1", "target": "e2", "mode": "on", "verification": "execution_error"}
    assert recent_failures(action, [failed, failed]) == (2, "execution_error")
    assert recent_failures(Candidate("place", "e1", "e3", "on"), [failed]) == (0, "none")
    assert recent_failures(action, [failed, {**failed, "verification": "verified"}]) == (0, "none")
    assert "failures=2:execution_error" in serialize("move", [entity()], .08, None, [failed]*2,
                                          choices=[action], failure_counts=True)


def test_compact_candidate_evidence_keeps_skill_identity_for_auxiliary_questions():
    failed = {"tool":"place", "object":"e1", "target":"e2", "mode":"on", "verification":"execution_error"}
    ordered = [Candidate("retreat"), Candidate("place","e1","e2","on")]
    state = serialize("move", [entity()], .08, None, [failed], choices=ordered, failure_counts=True)
    assert "candidate retreat() failures=0:none" in state
    assert "candidate place(e1,e2,on) failures=1:execution_error" in state
    interrupted = {"tool":"articulate", "object":"e1", "mode":"open", "executed":False, "stop":"execution_interrupted"}
    assert recent_failures(Candidate("articulate","e1",mode="open"),[interrupted]) == (1,"execution_interrupted")


def test_failed_place_creates_recovery_without_fabricating_a_target():
    a, b = entity(), entity("e2", "plate")
    receipt = {"tool": "place", "object": "e1", "target": "e2", "mode": "on", "error": "servo waypoint"}
    cs = candidates([a,b], "put bowl on plate", (0,0,.3), "e1", [receipt], random.Random(3), adjust_place=True)
    assert Candidate("adjust_place", "e1", "e2", "on") in cs
    absent = candidates([a], "put bowl on plate", (0,0,.3), None, [receipt], random.Random(3), adjust_place=True)
    assert not any(c.tool == "adjust_place" for c in absent)


def test_measured_cabinet_front_is_not_an_interior_placement_candidate():
    bowl = entity()
    front = Entity("e3","cabinet bottom drawer",(0,0,.14),(-.01,-.01,.1),(.01,.01,.18),
                   part_of="e4",geometry="measured_front_band")
    drawer = entity("e2","drawer")
    cs=candidates([bowl,front,drawer],"put bowl inside bottom drawer",(0,0,.3),"e1",[],random.Random(1))
    assert not any(c.tool == "place" and c.target == front.id for c in cs)
    assert Candidate("place","e1","e2","in") in cs


def test_strict_placement_rejects_a_stable_object_floating_above_support():
    plate = entity("e2", "plate", z=.1)
    floating = entity(z=.20)
    contact = entity(z=.12)
    assert not strict_place_verified(floating, floating, plate, .08, (0,0,.4), .31)
    assert strict_place_verified(contact, contact, plate, .08, (0,0,.4), .31)


def test_a_microwave_shell_does_not_verify_an_object_inside_its_projected_bounds():
    from robots.libero.v5_state import upgrade_controls
    from robots.libero.v5_verification import strict_place_verified_v3

    shell = Entity("e2", "microwave", (0, 0, .1), (-.1, -.1, 0), (.1, .1, .2))
    obj = entity("e1", "mug", .1)
    assert strict_place_verified(obj, obj, shell, .08, (0, 0, .4), .31, relation="in")
    assert strict_place_verified_v3(obj, obj, shell, .08, (0, 0, .4), .31, relation="in") is None
    actions = upgrade_controls([], [obj, shell], None, [{"tool": "place", "object": obj.id,
        "target": shell.id, "mode": "in", "place_verified": None, "verification": "unverified",
        "verification_reason": "interior_containment_not_measured"}], adjust_place=True)
    assert Candidate("adjust_place", obj.id, shell.id, "in") in actions


def test_table_region_checks_membership_without_claiming_object_support():
    from robots.libero.v5_verification import strict_place_verified_v3, strict_place_verified_v4

    obj = Entity("e1", "pudding", (.025, 0, .025), (-.01, -.03, 0), (.06, .03, .05))
    region = Entity("e2", "area right of plate", (0, 0, 0), (-.04, -.04, 0), (.04, .04, 0))
    assert not strict_place_verified_v3(obj, obj, region, .08, (0, 0, .4), .31)
    assert strict_place_verified_v4(obj, obj, region, .08, (0, 0, .4), .31)
    physical_support = Entity("e2", "plate", region.xyz, region.lower, region.upper)
    assert not strict_place_verified_v4(obj, obj, physical_support, .08, (0, 0, .4), .31)
    outside = Entity("e1", "pudding", (.07, 0, .025), (.04, -.03, 0), (.10, .03, .05))
    assert not strict_place_verified_v4(outside, outside, region, .08, (0, 0, .4), .31)
    assert not strict_place_verified_v4(obj, obj, region, .03, (0, 0, .4), .31)
    assert not strict_place_verified_v4(entity(z=.20), entity(z=.20), region, .08, (0, 0, .4), .31)


def test_drawer_receipt_with_numpy_camera_axes_is_json_serializable():
    before = Entity("e1", "cabinet bottom drawer", (0,0,.1), (-.1,-.1,0), (.1,.1,.2), source_step=1)
    after = Entity("e1", "cabinet bottom drawer", (0,-.03,.1), (-.1,-.13,0), (.1,.07,.2), source_step=2)
    verified, evidence = measured_articulation(before, after, "close", np.array([0.,1.,0.]))
    assert verified is True
    assert json.loads(json.dumps({"articulate_verified": verified, **evidence}))["articulate_verified"] is True


def test_endpoint_check_rejects_partial_drawer_close_even_after_correct_motion():
    def face(y):
        return vertical_face(np.array([(x,y,z) for x in np.linspace(-.1,.1,20)
                                       for z in np.linspace(.9,1.1,20)]))
    before = {"source_step":1, "frame":face(0), "moving":face(.1)}
    after = {"source_step":2, "frame":face(0), "moving":face(.06)}
    assert measured_fixture_endpoint(before, after, "close", drawer=True)[0] is False
    after["moving"] = face(.005)
    assert measured_fixture_endpoint(before, after, "close", drawer=True)[0] is True
    after["frame"] = face(.1)
    verified, evidence = measured_fixture_endpoint(before, after, "close", drawer=True)
    assert verified is None and evidence["reason"] == "reference_frame_not_stable"


def test_door_endpoint_uses_two_measured_planes_and_refuses_missing_evidence():
    def face(angle):
        return vertical_face(np.array([(x*np.cos(angle),x*np.sin(angle),z)
                                       for x in np.linspace(-.1,.1,20) for z in np.linspace(.9,1.1,20)]))
    before = {"source_step":1, "frame":face(0), "moving":face(0)}
    after = {"source_step":2, "frame":face(0), "moving":face(np.pi/3)}
    verified, evidence = measured_fixture_endpoint(before, after, "open", drawer=False)
    assert verified is True and abs(evidence["measured_door_angle_deg"]-60)<.001
    assert measured_fixture_endpoint(before, after, "close", drawer=False)[0] is False
    after["moving"] = None
    assert measured_fixture_endpoint(before, after, "open", drawer=False)[0] is None


def test_category_card_does_not_resolve_ambiguous_instances_or_wrong_held_object():
    card = {"version": VERSION, "origin": "original_oracle", "steps": [
        {"skill":"grasp", "object_category":"bowl", "mode":"direct"}]}
    validate_card(card)
    view = card_view(card, 0)
    assert resolve_card(view, [entity()], None) == Candidate("grasp", "e1", mode="direct")
    assert resolve_card(view, [entity(),entity("e2")], None) is None
    assert "xyz" not in view["next"]


def test_furniture_bands_come_from_current_depth_points_and_remain_in_parent_extent():
    parent = Entity("e1", "cabinet", (0,0,.3), (-.1,-.1,0), (.1,.1,.6))
    cloud=np.array([(x,y,z) for x in [-.1,0,.1] for y in [-.1,0,.1] for z in np.linspace(.01,.59,30)])
    parts = fixture_parts(parent, cloud, (1,0,0))
    assert {p['name'] for p in parts} >= {"cabinet top drawer","cabinet middle drawer","cabinet bottom drawer"}
    assert all(parent.lower[i] <= p['xyz'][i] <= parent.upper[i] for p in parts for i in range(3))
    assert not fixture_parts(parent, cloud[:2], (1,0,0))


def test_background_cabinet_below_the_measured_work_surface_is_rejected():
    parent = Entity("e55", "cabinet", (.08,.27,1.1), (-.12,.23,.92), (.12,.35,1.13))
    background = Entity("e62", "cabinet", (-1.39,-.49,.69), (-1.41,-.87,.38), (-1.36,-.26,.85))
    assert above_work_surface(parent, .91)
    assert not above_work_surface(background, .91)
    assert above_work_surface(background, None)
    cloud = np.array([[.08,.27,1.1],[-1.39,-.49,.69],[np.nan,0,0]])
    assert np.array_equal(fixture_points(cloud, parent), cloud[:1])


def test_work_surface_check_rejects_background_drawer_and_keeps_task_drawer():
    background = Entity("e5", "drawer", (-1.39,-.47,.62), (-1.40,-.79,.50), (-1.38,-.15,.75))
    working = Entity("e27", "drawer", (.01,.27,1.0), (-.1,.2,.94), (.12,.34,1.07))
    assert not above_work_surface(background,.91)
    assert above_work_surface(working,.91)


def test_flat_stove_surface_does_not_require_a_cabinet_height():
    stove = Entity("e2","stove",(0,0,.93),(-.08,-.08,.929),(.08,.08,.931))
    cloud = np.array([(x,y,.93) for x in np.linspace(-.08,.08,12) for y in np.linspace(-.08,.08,12)])
    parts = fixture_parts(stove,cloud,(1,0,0))
    assert [part['name'] for part in parts] == ['stove top surface']


def test_public_choices_roundtrip_without_code_execution():
    for action in [Candidate("place","e1","e2","in"),Candidate("grasp","e1",mode="direct"),Candidate("retreat")]:
        assert Candidate.from_text(action.text()) == action


def test_instruction_queries_keep_both_nouns_without_a_language_model():
    from robots.libero.v5_runtime import instruction_noun_phrases
    assert instruction_noun_phrases("Pick up the akita black bowl and place it in the top drawer of the cabinet.") == [
        "akita black bowl", "top drawer", "cabinet"]


def test_cabinet_front_comes_from_drawer_depth_not_the_camera_image_axis():
    from robots.libero.v5_fixture_parts import infer_cabinet_front
    levels = [(z, .07 if z < 1.0 else .22) for z in np.linspace(.93, 1.12, 45)]
    front = np.array([(x,y,z) for z,y in levels for x in np.linspace(-.1,.13,30)])
    side = np.array([(.13,y,z) for z in np.linspace(.93,1.12,45) for y in np.linspace(.22,.34,15)])
    cloud = np.vstack((front,side))
    axis, _ = infer_cabinet_front(cloud, (1.5,-.1,1.4))
    assert axis == (0.,-1.,0.)
    parent = Entity("e1","cabinet",(.05,.22,1.),(-.1,.07,.92),(.13,.34,1.13))
    parts = fixture_parts(parent,cloud,axis,calibrated_front=True)
    bottom = next(p for p in parts if p['name']=='cabinet bottom drawer')
    assert bottom['xyz'][1] < .10
    assert bottom['upper'][0] - bottom['lower'][0] > .18
    # Camera-X motion would mark this real closing movement as failure.
    before = Entity("e2","cabinet bottom drawer",(0,.07,.97),(-.1,.07,.93),(.13,.07,.99),source_step=0)
    after = Entity("e2","cabinet bottom drawer",(0,.22,.97),(-.1,.22,.93),(.13,.22,.99),source_step=1)
    assert measured_articulation(before,after,'close',axis)[0] is True
    assert measured_articulation(before,after,'close',None)[0] is None


def test_unmeasured_closed_cabinet_front_is_not_invented_and_calibration_persists():
    from robots.libero.v5_fixture_parts import infer_cabinet_front
    cloud = np.array([(x,.22,z) for z in np.linspace(.93,1.12,45) for x in np.linspace(-.1,.13,30)])
    assert infer_cabinet_front(cloud,(1.5,-.1,1.4))[0] is None
    parent = Entity("e1","cabinet",(0,.22,1.),(-.1,.22,.92),(.13,.22,1.13))
    assert all('drawer' not in p['name'] for p in fixture_parts(parent,cloud,None,calibrated_front=True))
    axis, _ = infer_cabinet_front(cloud,(1.5,-.1,1.4),(0.,-1.,0.))
    assert axis == (0.,-1.,0.)
def test_open_drawer_cloud_restores_front_profile_missing_from_cabinet_mask():
    from robots.libero.v5_fixture_parts import associated_drawers, infer_cabinet_front

    cabinet = Entity("e1", "cabinet", (0,.3,1), (-.12,.2,.9), (.12,.4,1.14))
    drawer = Entity("e2", "drawer", (0,.1,.94), (-.11,.05,.91), (.11,.21,.98))
    body = np.array([(x,.2,z) for x in np.linspace(-.12,.12,30)
                     for z in np.linspace(.91,1.13,50)])
    protruding = np.array([(x,.07,z) for x in np.linspace(-.11,.11,30)
                          for z in np.linspace(.91,.97,20)])
    assert associated_drawers(cabinet, [cabinet], [drawer]) == [drawer]
    assert infer_cabinet_front(body, (1,-1,2))[0] is None
    axis, _ = infer_cabinet_front(np.concatenate((body,protruding)), (1,-1,2))
    assert axis == (0.,-1.,0.)
    parts = fixture_parts(cabinet, np.concatenate((body,protruding)), axis, calibrated_front=True)
    bottom = next(p for p in parts if p['name'] == 'cabinet bottom drawer')
    assert bottom['xyz'][1] < .1
    other = Entity("e3", "cabinet", (0,.3,1), (-.12,.2,.9), (.12,.4,1.14))
    assert associated_drawers(cabinet, [cabinet, other], [drawer]) == []
