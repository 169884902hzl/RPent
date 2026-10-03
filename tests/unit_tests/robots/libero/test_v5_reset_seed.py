"""Fixtures and nested samplers must share the requested worker reset seed."""

from types import SimpleNamespace

import numpy as np

from robots.libero.v5_reset_seed import attach_reset_seed


def worker():
    child = SimpleNamespace(rng=np.random.default_rng())
    env = SimpleNamespace(rng=np.random.default_rng(), placement_initializer=
                          SimpleNamespace(rng=np.random.default_rng(), samplers={"fixture": child}))
    return SimpleNamespace(env=env, seed=lambda value: setattr(env, "seed", value)), child


def test_seed_controls_both_legacy_numpy_and_nested_generator_draws():
    draws = []
    for _ in range(2):
        wrapper, child = worker()
        attach_reset_seed(wrapper)
        wrapper.seed(81000)
        draws.append((np.random.uniform(size=4), child.rng.uniform(size=4)))
        assert child.rng is wrapper.env.rng
        assert wrapper.env.seed == 81000
    assert all(np.array_equal(a, b) for a, b in zip(draws[0], draws[1]))


def test_resetting_same_seed_repeats_but_another_seed_changes_the_sample():
    wrapper, child = worker()
    attach_reset_seed(wrapper)
    wrapper.seed(10)
    first = child.rng.uniform(size=4)
    wrapper.seed(10)
    assert np.array_equal(first, child.rng.uniform(size=4))
    wrapper.seed(11)
    assert not np.array_equal(first, child.rng.uniform(size=4))
