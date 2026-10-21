"""Readonly async preparation and safe adoption of late/stale choices."""
import copy
import threading
from types import SimpleNamespace

from robots.libero.bounded_async import AsyncSkillDecisions
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision


def test_model_view_preserves_conditional_transport_and_all_legal_prefixes(adapter):
    from robots.libero.bounded_async import public_model_request
    from rpent.skill_package.contract import legal_after, validate

    request = adapter.request(k=4)
    blocked = copy.deepcopy(request['candidates'][0])
    blocked['id'] = 'blocked-collision'
    blocked['consequences'].update(collision=True)
    unreachable = copy.deepcopy(blocked)
    unreachable['id'] = 'blocked-ik'
    unreachable['consequences'].update(collision=False, ik_reachable=False)
    transport = next(c for c in request['candidates'] if c['skill'] == 'carry_to')
    transport['consequences'].update(collision=None, ik_reachable=None,
        screen_scope='conditional_on_prefix')
    request['candidates'] += [blocked, unreachable]
    before = copy.deepcopy(request)
    view = public_model_request(request)
    validate(view)
    assert request == before
    assert transport in view['candidates']
    assert not {'blocked-collision', 'blocked-ik'} & {c['id'] for c in view['candidates']}
    # Exercise held-state transitions as well as initial legality.
    prefixes = [()]
    for _ in range(3):
        following = []
        for prefix in prefixes:
            assert legal_after(view, prefix) == legal_after(request, prefix)
            following.extend(prefix+(cid,) for cid in legal_after(request, prefix))
        prefixes = following


def test_http_omits_only_frozen_blockers_and_validates_source_ids(adapter, monkeypatch):
    from io import StringIO
    import json
    from robots.libero.bounded_async import http_choice, public_model_request
    request = adapter.request(k=1)
    first = request['candidates'][0]
    blocked = copy.deepcopy(first)
    blocked['id'] = 'blocked'
    blocked['consequences']['collision'] = True
    request['candidates'].append(blocked)
    def receive(call, **kwargs):
        payload = json.loads(call.data)
        assert payload['skill_request'] == public_model_request(request)
        return StringIO(json.dumps({'decision': decision(request, [first['id']])}))
    monkeypatch.setattr('robots.libero.bounded_async.urlopen', receive)
    assert http_choice('http://offline')(request) == decision(request, [first['id']])


def moving_request(adapter, request, first, monkeypatch):
    adapter.geometry['site_offset_in_gripper_m'] = [0., 0., 0.]
    adapter._base_geometry = ([], None)
    monkeypatch.setattr('robots.libero.bounded_skills.PublicPoseScreen', lambda *args, **kwargs: None)
    adapter._executing_prefix = {'request': request, 'choices': [first], 'completed': 0}
    try:
        snapshot = adapter.snapshot_decision_context(remaining_reference_s=.5)
        return snapshot['build_request']()
    finally:
        adapter._executing_prefix = None


def test_async_worker_never_reads_live_environment(adapter, monkeypatch):
    execution_thread = threading.get_ident()
    original = adapter.p.env.raw_obs
    def public_obs():
        assert threading.get_ident() == execution_thread
        return original()
    adapter.p.env.raw_obs = public_obs
    adapter.geometry["site_offset_in_gripper_m"] = [0., 0., 0.]
    adapter._base_geometry = ([], None)
    monkeypatch.setattr("robots.libero.bounded_skills.PublicPoseScreen", lambda *args, **kwargs: None)
    request = adapter.request(k=4)
    def frozen_screen(*args, **kwargs):
        return lambda poses: {"passed": True, "reason": "frozen_geometry", "collision": False,
            "ik_reachable": True, "path_min_clearance_m": .05}
    monkeypatch.setattr(type(adapter), "_cloud_and_ik", frozen_screen)
    del adapter._cloud_and_ik
    worker_threads = []
    def choose(request):
        worker_threads.append(threading.get_ident())
        return decision(request, [request["candidates"][0]["id"]])
    loop = AsyncSkillDecisions(choose, decision_latency_s=1.)
    try:
        loop.poll(2., adapter.snapshot_decision_context)
        assert loop.pending is None
        loop.poll(.5, adapter.snapshot_decision_context)
        adapter.revision += 1
        prefetched = loop.take(adapter, wait=True)
        assert prefetched is not None
        assert worker_threads[0] != execution_thread
        assert prefetched[0]["revision"] == request["revision"]+1
    finally:
        loop.close()


def test_stale_geometry_discards_readonly_result(adapter):
    request = adapter.request(k=1)
    frozen = copy.deepcopy(request)
    frozen["revision"] += 1
    loop = AsyncSkillDecisions(lambda req: decision(req, [req["candidates"][0]["id"]]), decision_latency_s=1.)
    try:
        loop.poll(.5, lambda **kwargs: {"sim_step": 0, "build_request": lambda: frozen})
        adapter.revision += 1
        adapter.scene.entities.clear()
        assert loop.take(adapter, wait=True) is None
        assert loop.events[-1]["discarded"] == "public_geometry_or_revision_changed"
    finally:
        loop.close()


def test_pending_at_rest_endpoint_is_a_completed_motion(adapter):
    class Pending:
        def __init__(self):
            self.pending = (None, SimpleNamespace(done=lambda: False))
        def poll(self, remaining, factory):
            pass
    request = adapter.request(k=1)
    nudge = next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": "x", "distance_m": .01})
    receipt = adapter.execute(request, decision(request, [nudge["id"]]), async_decisions=Pending())[0]
    assert receipt["outcome"] == "success"
    assert receipt["stop_reason"] == "decision_pending_at_rest_endpoint"


def test_stable_objects_do_not_allow_stale_robot_budget_or_receipts(adapter):
    request = adapter.request(k=1)
    frozen = copy.deepcopy(request)
    frozen['revision'] += 1
    move = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .02})
    adapter.execute(request, decision(request, [move['id']]))
    assert not adapter.adopt_prefetched(frozen)


def test_moving_prefetch_rechecks_selected_route_and_keeps_source_measurement(adapter, monkeypatch):
    request = adapter.request(k=1)
    first = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .02})
    frozen = moving_request(adapter, request, first, monkeypatch)
    following = next(c for c in frozen['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .01})
    adapter.execute(request, decision(request, [first['id']]))
    chosen = decision(frozen, [following['id']])
    assert adapter.adopt_prefetched(frozen, chosen)
    assert frozen['robot']['eef_xyz_m'][0] == 0.  # Keep its true source timestamp/pose.
    prefix = frozen['execution_prefix']
    assert prefix['steps'] == [{key: first[key] for key in ('id', 'skill', 'parameters')}]
    assert prefix['predicted_state']['robot']['eef_xyz_m'][0] == .02
    assert prefix['predicted_state']['remaining_sim_steps'] < frozen['remaining_sim_steps']
    assert following['consequences']['expected_steps'] > 0
    assert adapter.last_prefetch_adoption['current_remaining_sim_steps'] < frozen['remaining_sim_steps']
    receipt = adapter.execute(frozen, chosen)[0]
    assert receipt['outcome'] == 'success'
    assert abs(receipt['after']['eef_xyz_m'][0]-.02) < 1e-8
    assert abs(receipt['after']['eef_xyz_m'][1]-.01) < 1e-8


def test_moving_prefetch_rejects_a_new_collision_and_contact_transition(adapter, monkeypatch):
    request = adapter.request(k=1)
    move = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .01})
    frozen = moving_request(adapter, request, move, monkeypatch)
    following = next(c for c in frozen['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .01})
    adapter.execute(request, decision(request, [move['id']]))
    adapter._cloud_and_ik = lambda *args, **kwargs: lambda poses: {
        'passed': False, 'reason': 'measured_sweep_collision', 'collision': True,
        'ik_reachable': None, 'path_min_clearance_m': 0.}
    assert not adapter.adopt_prefetched(frozen, decision(frozen, [following['id']]))

    request = adapter.request(k=1)
    frozen = copy.deepcopy(request)
    frozen['revision'] += 1
    gripper = next(c for c in request['candidates'] if c['skill'] == 'set_gripper'
        and c['parameters']['mode'] == 'close')
    adapter.execute(request, decision(request, [gripper['id']]))
    assert not adapter.adopt_prefetched(frozen, decision(frozen, [gripper['id']]))


def test_moving_prefetch_rejects_unfulfilled_or_different_commitment(adapter, monkeypatch):
    request = adapter.request(k=1)
    move = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .02})
    frozen = moving_request(adapter, request, move, monkeypatch)
    following = next(c for c in frozen['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .01})
    chosen = decision(frozen, [following['id']])
    adapter.execute(request, decision(request, [move['id']]))
    valid = copy.deepcopy(frozen)
    frozen['execution_prefix']['predicted_state']['robot']['eef_xyz_m'][0] += .03
    assert not adapter.adopt_prefetched(frozen, chosen)
    frozen = copy.deepcopy(valid)
    frozen['execution_prefix']['source_observation_id'] = 'other-source'
    assert not adapter.adopt_prefetched(frozen, chosen)
    frozen = copy.deepcopy(valid)
    frozen['execution_prefix']['steps'][0]['id'] = 'another-step'
    assert not adapter.adopt_prefetched(frozen, chosen)
    adapter._last_free_chunk = None  # Interrupted source chunks discard their promise.
    assert not adapter.adopt_prefetched(valid, chosen)


def test_inflight_relative_move_predicts_committed_endpoint_not_another_delta(adapter, monkeypatch):
    request = adapter.request(k=4)
    x = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .02})
    y = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .01})
    snapshots = []
    original = adapter.snapshot_decision_context
    def freeze(**kwargs):
        result = original(**kwargs)
        snapshots.append(result)
        return result
    adapter.snapshot_decision_context = freeze
    adapter.geometry['site_offset_in_gripper_m'] = [0., 0., 0.]
    monkeypatch.setattr('robots.libero.bounded_skills.PublicPoseScreen', lambda *args, **kwargs: None)
    class Lookahead:
        pending = None
        def poll(self, remaining, factory):
            if not snapshots and adapter.robot()['eef_xyz_m'][0] > .001:
                factory(remaining_reference_s=remaining)
    adapter.execute(request, decision(request, [x['id'], y['id']]), async_decisions=Lookahead())
    assert snapshots
    frozen = snapshots[0]['build_request']()
    assert 0. < frozen['robot']['eef_xyz_m'][0] < .02
    predicted = frozen['execution_prefix']['predicted_state']['robot']['eef_xyz_m']
    assert abs(predicted[0]-.02) < 1e-9
    assert abs(predicted[1]-.01) < 1e-9
    assert [s['id'] for s in frozen['execution_prefix']['steps']] == [x['id'], y['id']]
