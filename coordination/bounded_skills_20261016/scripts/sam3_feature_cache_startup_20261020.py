"""Prototype a bounded cache of immutable SAM image features across episodes."""

import argparse
import hashlib
import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path


def copy_containers(value):
    """Detach prompt-mutable containers while retaining read-only image tensors."""
    if isinstance(value, dict):
        return {key: copy_containers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_containers(item) for item in value]
    if isinstance(value, tuple):
        return tuple(copy_containers(item) for item in value)
    return value


class ImageFeatureCache:
    """Preserve the original consecutive-image state and fresh-state resets."""

    def __init__(self, *args, image_cache_entries=32, **kwargs):
        if image_cache_entries < 1:
            raise ValueError('image_cache_entries must be positive')
        self._image_cache_entries = image_cache_entries
        self._image_templates = OrderedDict()
        self._image_cache_hits = self._image_cache_misses = 0
        super().__init__(*args, **kwargs)

    def _state_for_image(self, image_bytes):
        digest = hashlib.sha256(image_bytes).hexdigest()
        # Consecutive text/point RPCs retain the frozen facade's state contract.
        if digest == self._image_digest and self._image_state is not None:
            self._image_cache_hits += 1
            return self._image_state
        if digest in self._image_templates:
            self._image_templates.move_to_end(digest)
            state = copy_containers(self._image_templates[digest])
            self._image_digest, self._image_state = digest, state
            self._image_cache_hits += 1
            return state
        state = super()._state_for_image(image_bytes)
        # Capture immediately after set_image, before text, geometry prompts,
        # masks or scores are installed by the requesting RPC.
        self._image_templates[digest] = copy_containers(state)
        while len(self._image_templates) > self._image_cache_entries:
            self._image_templates.popitem(last=False)
        self._image_cache_misses += 1
        logging.info('image_feature_cache hits=%d misses=%d entries=%d',
            self._image_cache_hits, self._image_cache_misses, len(self._image_templates))
        return state


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--image-cache-entries', type=int, default=32)
    startup, remaining = parser.parse_known_args()
    source = startup.source.resolve(strict=True)
    sys.path.insert(0, str(source))
    from coordination.bounded_skills_20261016.scripts.sam3_output_filter_startup_20261020 import (
        EarlyOutputFilter,
    )
    from robots.libero.v5_sam3_server import V5Sam3Facade, _build_argparser

    args = _build_argparser().parse_args(remaining)
    logging.basicConfig(level=logging.INFO)
    if args.cuda_device is not None:
        os.environ['CUDA_VISIBLE_DEVICES'] = str(args.cuda_device)
    facade_type = type('CachedImageSam3Facade', (ImageFeatureCache, EarlyOutputFilter, V5Sam3Facade), {})
    facade = facade_type(os.environ['SAM3_CHECKPOINT_PATH'], image_cache_entries=startup.image_cache_entries)
    facade.serve(transport=args.transport, host=args.host, port=args.port, parent_watch=args.parent_watch)


if __name__ == '__main__':
    main()
