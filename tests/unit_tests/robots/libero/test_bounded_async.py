"""Readonly async preparation and safe adoption of late/stale choices."""
import copy
import threading
from types import SimpleNamespace

from robots.libero.bounded_async import AsyncSkillDecisions
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision


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
        loop.poll(.5, lambda: {"sim_step": 0, "build_request": lambda: frozen})
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
