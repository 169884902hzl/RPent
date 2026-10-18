"""Exclusive wall-time attribution for the development feasibility runner."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from threading import Lock, get_ident, local
from time import perf_counter


class EpisodeTimings:
    """Keep nested timers disjoint; report worker overlap separately."""

    def __init__(self, clock=perf_counter):
        self.clock = clock
        self.started = clock()
        self.main_thread = get_ident()
        self.threads = local()
        self.lock = Lock()
        self.events = []
        self.originals = []

    @contextmanager
    def measure(self, category, hook=None):
        stack = getattr(self.threads, 'stack', [])
        self.threads.stack = stack
        entry = [self.clock(), 0.]
        stack.append(entry)
        try:
            yield
        finally:
            elapsed = self.clock()-entry[0]
            stack.pop()
            if stack:
                stack[-1][1] += elapsed
            event = dict(category=category, hook=hook, thread=get_ident(),
                start_s=entry[0]-self.started, inclusive_s=elapsed,
                exclusive_s=max(0., elapsed-entry[1]))
            with self.lock:
                self.events.append(event)

    def wrap(self, owner, name, category):
        """Wrap the actual owner; class methods keep their normal binding."""
        original = getattr(owner, name)
        @wraps(original)
        def timed(*args, **kwargs):
            with self.measure(category, name):
                return original(*args, **kwargs)
        self.originals.append((owner, name, original))
        setattr(owner, name, timed)

    def close(self):
        for owner, name, original in reversed(self.originals):
            setattr(owner, name, original)
        self.originals.clear()

    def summary(self, wall_s):
        totals = defaultdict(float)
        main = defaultdict(float)
        calls = defaultdict(int)
        for event in self.events:
            totals[event['category']] += event['exclusive_s']
            calls[event['category']+':'+str(event['hook'])] += 1
            if event['thread'] == self.main_thread:
                main[event['category']] += event['exclusive_s']
        return dict(version='bounded-wall-time/1', wall_s=wall_s,
            main_thread_exclusive_s=dict(main), all_threads_exclusive_s=dict(totals),
            main_thread_unattributed_s=max(0., wall_s-sum(main.values())), calls=dict(calls),
            worker_times_overlap_main_thread=True,
            scope='client wall time including transport; initial simulator construction excluded')


def install_episode_timers(timings, *, tools, env, toolkit, scene, model=None):
    """Instrument owned calls without changing observations or execution."""
    from robots.libero.bounded_chunk import PublicPrefixPrediction
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen

    for name in ('step', 'chunk_step', 'render_camera'):
        timings.wrap(env, name, 'simulation.step_render')
    for name in ('_metric_depth', '_world_from_depth'):
        timings.wrap(tools, name, 'perception.depth')
    timings.wrap(toolkit, 'get_env_state', 'perception.capture_io')
    timings.wrap(scene.rpc, 'call', 'perception.segmentation')
    for name in ('refresh', 'measure_fixture_handle_pose', 'measure_fixture_endpoint'):
        timings.wrap(type(scene), name, 'perception.entity_measurement')
    for name in ('_instance_pixels', '_contact_pixels', '_refresh_held_measurement'):
        timings.wrap(MeasuredSkillAdapter, name, 'perception.entity_measurement')
    for name in ('_candidate', '_cloud_and_ik', '_route', 'plan_chunk', 'prefix_context'):
        timings.wrap(MeasuredSkillAdapter, name, 'planning.consequences')
    timings.wrap(MeasuredSkillAdapter, '_record_public_geometry', 'artifact_io')
    timings.wrap(PublicPrefixPrediction, 'context', 'planning.consequences')
    timings.wrap(PublicRouteScreen, '__call__', 'planning.consequences')
    timings.wrap(PublicPoseScreen, 'check', 'planning.consequences')
    if model is not None:
        timings.wrap(model, 'predict', 'vla.inference')
