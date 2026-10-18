"""Profiling keeps real perception calls and errors intact."""
import pstats
from types import SimpleNamespace

import pytest

from scripts.probe_bounded_feasibility import profile_perception_refresh


def test_profile_retains_exact_arguments_result_and_error(tmp_path):
    calls = []
    result = object()

    def original(names, *, fail=False):
        calls.append((names, fail))
        if fail:
            raise ValueError('original failure')
        return result

    scene = SimpleNamespace(refresh=original)
    profile_perception_refresh(scene, tmp_path)
    names = ['bowl', 'plate']
    assert scene.refresh(names) is result
    with pytest.raises(ValueError, match='original failure'):
        scene.refresh(names, fail=True)
    assert all(call[0] is names for call in calls)
    assert calls == [(names, False), (names, True)]
    for i in range(2):
        stats = pstats.Stats(str(tmp_path/f'perception_refresh_{i:03d}.pstats'))
        assert any(key[2] == 'original' and value[1] == 1 for key, value in stats.stats.items())
