# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Unaliased RGB-D measurements in an owned LIBERO rendering worker."""
from __future__ import annotations

import types


def render_measurement(wrapper, camera_name, height, width):
    """Render one RGB/depth pair without resolving mixed depth edge samples.

    Reuse the worker's current GL context and camera. A temporary framebuffer
    has zero multisamples; the normal policy framebuffer and model settings
    are restored even if rendering fails. No simulation step is performed.
    """
    import mujoco

    sim = wrapper.env.sim
    renderer = sim._render_context_offscreen
    renderer.gl_ctx.make_current()
    original = renderer.con
    visual = sim.model.vis
    settings = visual.quality.offsamples, visual.global_.offwidth, visual.global_.offheight
    try:
        visual.quality.offsamples = 0
        visual.global_.offwidth = max(int(width), int(settings[1]))
        visual.global_.offheight = max(int(height), int(settings[2]))
        measurement = mujoco.MjrContext(sim.model._model, mujoco.mjtFontScale.mjFONTSCALE_150)
    finally:
        visual.quality.offsamples, visual.global_.offwidth, visual.global_.offheight = settings
    try:
        renderer.con = measurement
        mujoco.mjr_setBuffer(mujoco.mjtFramebuffer.mjFB_OFFSCREEN, measurement)
        return sim.render(width=int(width), height=int(height), camera_name=camera_name, depth=True)
    finally:
        renderer.con = original
        measurement.free()
        mujoco.mjr_setBuffer(mujoco.mjtFramebuffer.mjFB_OFFSCREEN, original)


def attach_measurement_renderer(wrapper):
    """Expose the owned public camera operation through the existing worker."""
    wrapper.bounded_render_measurement = types.MethodType(render_measurement, wrapper)
    return wrapper
