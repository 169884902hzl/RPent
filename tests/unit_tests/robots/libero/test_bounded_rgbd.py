# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measurement rendering must not alter the policy framebuffer or physics."""
import sys
from types import SimpleNamespace

import pytest

from robots.libero.bounded_rgbd import attach_measurement_renderer
from robots.libero.v5_env_server import V5EnvFacade


@pytest.mark.parametrize('failure', [None, 'construct', 'render'])
def test_single_sample_measurement_restores_policy_context_and_settings(monkeypatch, failure):
    quality = SimpleNamespace(offsamples=4)
    dimensions = SimpleNamespace(offwidth=640, offheight=480)
    model = SimpleNamespace(vis=SimpleNamespace(quality=quality, global_=dimensions), _model=object())
    normal = object()
    freed, buffers, rendered = [], [], []
    temporary = SimpleNamespace(free=lambda: freed.append(True))
    renderer = SimpleNamespace(con=normal, gl_ctx=SimpleNamespace(make_current=lambda: None))

    def create(*args):
        assert (quality.offsamples, dimensions.offwidth, dimensions.offheight) == (0, 1024, 1024)
        if failure == 'construct':
            raise RuntimeError('construct')
        return temporary

    def render(**kwargs):
        assert renderer.con is temporary
        assert (quality.offsamples, dimensions.offwidth, dimensions.offheight) == (4, 640, 480)
        rendered.append(kwargs)
        if failure == 'render':
            raise RuntimeError('render')
        return 'rgb', 'depth'

    monkeypatch.setitem(sys.modules, 'mujoco', SimpleNamespace(MjrContext=create,
        mjtFontScale=SimpleNamespace(mjFONTSCALE_150=150),
        mjtFramebuffer=SimpleNamespace(mjFB_OFFSCREEN=1),
        mjr_setBuffer=lambda _, context: buffers.append(context)))
    sim = SimpleNamespace(model=model, _render_context_offscreen=renderer, render=render)
    wrapper = attach_measurement_renderer(SimpleNamespace(env=SimpleNamespace(sim=sim)))
    if failure:
        with pytest.raises(RuntimeError, match=failure):
            wrapper.bounded_render_measurement('agentview', 1024, 1024)
    else:
        assert wrapper.bounded_render_measurement('agentview', 1024, 1024) == ('rgb', 'depth')
    assert renderer.con is normal
    assert (quality.offsamples, dimensions.offwidth, dimensions.offheight) == (4, 640, 480)
    assert bool(freed) == (failure != 'construct')
    if failure != 'construct':
        assert buffers == [temporary, normal]
        assert rendered == [{'width': 1024, 'height': 1024, 'camera_name': 'agentview', 'depth': True}]


def test_facade_routes_only_enabled_rgbd_calls_to_measurement_worker(monkeypatch):
    calls = []
    facade = V5EnvFacade.__new__(V5EnvFacade)
    facade._env = SimpleNamespace(env=SimpleNamespace(workers=[SimpleNamespace(
        env_call=lambda *args, **kwargs: calls.append((args, kwargs)) or ('rgb', 'depth'))]))
    facade._rgbd_no_msaa_v1 = True
    assert facade.render_camera('wrist', height=1024, width=1024, depth=True) == ('rgb', 'depth')
    assert calls == [(('bounded_render_measurement',), {'args': ['wrist', 1024, 1024], 'target': 'self'})]
    legacy = []
    monkeypatch.setattr('robots.libero.env_server.LiberoEnvFacade.render_camera',
        lambda *args, **kwargs: legacy.append(kwargs) or 'normal')
    assert facade.render_camera('wrist', depth=False) == 'normal'
    facade._rgbd_no_msaa_v1 = False
    assert facade.render_camera('wrist', depth=True) == 'normal'
    assert [call['depth'] for call in legacy] == [False, True]
    assert len(calls) == 1
