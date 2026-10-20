"""Image-cache hits reproduce a fresh image after an intervening frame."""

import pytest

from coordination.bounded_skills_20261016.scripts.sam3_feature_cache_startup_20261020 import (
    ImageFeatureCache,
)


class FrozenImageFacade:
    def __init__(self):
        self._image_digest = self._image_state = None
        self.encodes = 0

    def _state_for_image(self, image_bytes):
        import hashlib

        if image_bytes == b'invalid':
            raise ValueError('invalid image data')
        self.encodes += 1
        self._image_digest = hashlib.sha256(image_bytes).hexdigest()
        self._image_state = {'backbone_out': {'features': [image_bytes]}, 'height': 2}
        return self._image_state


class CachedImageFacade(ImageFeatureCache, FrozenImageFacade):
    pass


def test_interleaving_detaches_nested_prompt_state_without_reencoding_image():
    facade = CachedImageFacade()
    a = facade._state_for_image(b'a')
    a['backbone_out']['language'] = 'first prompt'
    a['backbone_out']['features'].append('prompt mutation')
    a['masks'] = 'large mask output'
    facade._state_for_image(b'b')['backbone_out']['language'] = 'other episode'
    restored = facade._state_for_image(b'a')
    assert restored == {'backbone_out': {'features': [b'a']}, 'height': 2}
    assert facade.encodes == 2
    assert facade._state_for_image(b'a') is restored
    assert facade._image_cache_hits == 2 and facade._image_cache_misses == 2


def test_lru_eviction_recomputes_only_the_evicted_image():
    facade = CachedImageFacade(image_cache_entries=2)
    for image in (b'a', b'b', b'a', b'c', b'a'):
        facade._state_for_image(image)
    assert facade.encodes == 3 and len(facade._image_templates) == 2
    facade._state_for_image(b'b')
    assert facade.encodes == 4


def test_consecutive_image_retains_existing_point_and_text_prompt_state():
    facade = CachedImageFacade()
    state = facade._state_for_image(b'a')
    state['point_prompt'] = [1, 2]
    assert facade._state_for_image(b'a') is state
    assert facade._state_for_image(b'a')['point_prompt'] == [1, 2]


def test_invalid_image_does_not_install_a_cache_entry():
    facade = CachedImageFacade()
    with pytest.raises(ValueError, match='invalid image'):
        facade._state_for_image(b'invalid')
    assert not facade._image_templates and facade._image_cache_misses == 0


def test_nonpositive_capacity_is_rejected():
    with pytest.raises(ValueError, match='positive'):
        CachedImageFacade(image_cache_entries=0)
