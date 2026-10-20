"""Async encoding preserves array ownership and exposes write failures."""
import copy

import numpy as np
import pytest

from robots.libero.bounded_artifacts import AsyncEnvState


def test_pending_array_is_owned_and_reads_and_checkpoint_flush_are_exact(tmp_path):
    state = AsyncEnvState(tmp_path,lossless_compression_level=1)
    image = np.full((64,64,3),127,dtype=np.uint8)
    points = np.arange(64*64*3).reshape(64,64,3).astype(np.float32)
    state.save('image.png',image,step=None)
    state.save('world.npz',points,step=None)
    image[:] = 0
    points[:] = 0
    np.testing.assert_array_equal(state.load('image.png',step=None),np.full((64,64,3),127))
    np.testing.assert_array_equal(state.load('world.npz',step=None),np.arange(64*64*3).reshape(64,64,3))
    state.flush()
    copy.deepcopy(vars(state))  # No executor, future or lock enters a snapshot.
    state.close()


def test_background_error_is_observed_at_read_and_not_reported_as_complete(tmp_path,monkeypatch):
    import robots.libero.bounded_artifacts as artifacts
    def fail(*args):
        raise OSError('disk failure')
    monkeypatch.setattr(artifacts,'_write_array',fail)
    state = AsyncEnvState(tmp_path)
    state.save('world.npz',np.ones(3),step=None)
    with pytest.raises(OSError,match='disk failure'):
        state.load('world.npz',step=None)
    state.close()


def test_capture_array_cache_preserves_fresh_read_ownership_and_save_invalidation(tmp_path):
    state = AsyncEnvState(tmp_path,lossless_compression_level=1)
    name = 'agentview_world_high.npz'
    state.save(name,np.ones((3,3,3)),step=None)
    read = state.load(name,step=None)
    read[:] = 42
    assert np.array_equal(state.load(name,step=None),np.ones((3,3,3)))
    state.save(name,np.full((3,3,3),2.),step=None)
    assert np.array_equal(state.load(name,step=None),np.full((3,3,3),2.))
    assert not any('cache' in key for key in vars(state))
    state.close()
