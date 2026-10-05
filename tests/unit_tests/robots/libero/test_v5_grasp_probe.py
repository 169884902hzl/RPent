"""The diagnostic RPent stop must not replace measured grasp verification."""

from types import SimpleNamespace

import pytest

from scripts.probe_v5_grasp449_20261005 import rpent_pick_then_measure


@pytest.mark.parametrize("primitive_success,visual_success", [(True, False), (False, True), (True, True)])
def test_rpent_stop_uses_public_primitive_but_visual_receipt(primitive_success, visual_success):
    calls = []
    primitive = {"chunks_used": 12, "success": primitive_success}
    obj = SimpleNamespace(name="bowl")
    executor = SimpleNamespace(
        p=SimpleNamespace(pi0_pick=lambda prompt, **kwargs:
                          calls.append((prompt, kwargs)) or primitive),
        _refresh=lambda names: calls.append(names),
        verify_grasp_measurement=lambda before: visual_success)
    receipt, recorded = rpent_pick_then_measure(executor, "pick up the bowl", 160, obj)
    assert calls == [("pick up the bowl", {"max_chunks": 160}), ["bowl"]]
    assert receipt["grasp_verified"] is visual_success
    assert receipt["chunks"] == 12
    assert recorded == primitive
