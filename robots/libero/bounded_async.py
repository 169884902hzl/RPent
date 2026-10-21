"""Overlap readonly public-option preparation and a caller-owned decision service.

The execution thread freezes public measurements. The worker never touches the
simulator; late decisions are consumed at rest and stale geometry is rejected.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import time
from urllib.request import Request, urlopen

from rpent.skill_package.contract import selected


class AsyncSkillDecisions:
    def __init__(self, choose, *, decision_latency_s: float, preparation_latency_s: float = 0.):
        if min(decision_latency_s, preparation_latency_s) < 0:
            raise ValueError("latency estimates must be nonnegative")
        self.choose = choose
        self.lead_s = decision_latency_s+preparation_latency_s
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bounded-decisions")
        self.pending = None
        self.events = []

    def poll(self, remaining_s, snapshot_factory):
        if self.pending is not None or remaining_s > self.lead_s:
            return
        snapshot = snapshot_factory(remaining_reference_s=remaining_s)
        event = {"submitted_wall_s": time.perf_counter(), "remaining_reference_s": remaining_s,
                 "public_sim_step": snapshot["sim_step"], "lead_estimate_s": self.lead_s}
        self.events.append(event)
        def prepare_and_choose():
            request = snapshot["build_request"]()
            event["prepared_wall_s"] = time.perf_counter()
            decision = self.choose(request)
            selected(request, decision)
            event["decision_ready_wall_s"] = time.perf_counter()
            return request, decision
        self.pending = snapshot, self.worker.submit(prepare_and_choose)

    def take(self, adapter, *, wait=False):
        if self.pending is None or (not wait and not self.pending[1].done()):
            return None
        (_, future), self.pending = self.pending, None
        request, decision = future.result()
        # This check runs on the execution thread after its measured refresh.
        if not adapter.adopt_prefetched(request, decision):
            self.events[-1]["discarded"] = "public_geometry_or_revision_changed"
            return None
        self.events[-1]["consumed_wall_s"] = time.perf_counter()
        if adapter.last_prefetch_adoption is not None:
            self.events[-1]['endpoint_revalidation'] = adapter.last_prefetch_adoption
        return request, decision

    def close(self):
        self.worker.shutdown(wait=True, cancel_futures=True)


def public_model_request(request: dict) -> dict:
    """Omit frozen collision/IK blockers without removing any legal prefix.

    Conditional transport options stay present: a predecessor may establish
    their held-object precondition. The public contract excludes the removed
    blockers for every prefix of this observation, independently of the task.
    """
    candidates = [candidate for candidate in request['candidates']
        if candidate['consequences']['collision'] is not True
        and candidate['consequences']['ik_reachable'] is not False]
    return dict(request, candidates=candidates)


def http_choice(endpoint: str, *, timeout_s: float = 120.):
    """Codex2's bounded-choice endpoint; no model or oracle is hidden here."""
    def choose(request):
        body = json.dumps({"skill_request": public_model_request(request),
            "k": request["max_actions"], "mode": "cached"}).encode()
        call = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(call, timeout=timeout_s) as response:
            result = json.load(response)
        # Accept only the service's explicitly returned source decision.
        decision = result["decision"] if "decision" in result else result
        selected(request, decision)
        return decision
    return choose
