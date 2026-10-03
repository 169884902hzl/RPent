# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Seed both LIBERO legacy samplers and Robosuite 1.5 sampler generators."""

import types

import numpy as np


def attach_reset_seed(wrapper):
    """Extend the owned worker's seed method, without changing installed assets.

    LIBERO MultiRegionRandomSampler still uses the global NumPy RNG; upstream
    Robosuite samplers use their own generators. Replacing only env.rng leaves
    both paths uncontrolled. Static fixture body poses are absent from qpos.
    """
    original_seed = wrapper.seed

    def seed(self, value):
        original_seed(value)
        np.random.seed(int(value) % (2**32))
        rng = np.random.default_rng(int(value))
        self.env.rng = rng

        def visit(sampler):
            if sampler is None:
                return
            if hasattr(sampler, "rng"):
                sampler.rng = rng
            for child in getattr(sampler, "samplers", {}).values():
                visit(child)

        for name in ("placement_initializer", "conditional_placement_initializer",
                     "conditional_placement_on_objects_initializer"):
            visit(getattr(self.env, name, None))

    wrapper.seed = types.MethodType(seed, wrapper)
    return wrapper
