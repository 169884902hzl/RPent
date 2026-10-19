# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Start the frozen SAM facade with equivalent early multi-mask filtering."""

import argparse
import logging
import os
import sys
import threading
from pathlib import Path


def conservative_cutoff(min_score):
    """Keep every score accepted by the original CPU float comparison."""
    if min_score == 0:
        return 0.
    import torch

    # The frozen model can produce bfloat16 probabilities. A Python scalar
    # rounds to that dtype during the processor's strict `>` comparison.
    # One representable bfloat16 value below the requested cutoff retains
    # all originally accepted scores, including exact boundary values.
    return float(torch.nextafter(torch.tensor(min_score, dtype=torch.bfloat16),
        torch.tensor(float('-inf'), dtype=torch.bfloat16)))


class EarlyOutputFilter:
    """Prune only proposals that the unchanged segment_all would discard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def segment_all(self, image_base64, text_prompt, min_score=.2):
        if not 0 <= min_score <= 1:
            raise ValueError('invalid text prompt / confidence')
        with self._lock:
            previous = self._processor.confidence_threshold
            self._processor.confidence_threshold = conservative_cutoff(min_score)
            try:
                return super().segment_all(image_base64, text_prompt, min_score)
            finally:
                # segment()/point RPCs retain the frozen facade's behavior,
                # including its below-cutoff score and reason fields.
                self._processor.confidence_threshold = previous


def main():
    source_parser = argparse.ArgumentParser(add_help=False)
    source_parser.add_argument('--source', type=Path, required=True)
    source_args, remaining = source_parser.parse_known_args()
    sys.path.insert(0, str(source_args.source.resolve(strict=True)))
    from robots.libero.v5_sam3_server import V5Sam3Facade, _build_argparser

    args = _build_argparser().parse_args(remaining)
    logging.basicConfig(level=logging.INFO)
    if args.cuda_device is not None:
        os.environ['CUDA_VISIBLE_DEVICES'] = str(args.cuda_device)
    facade_type = type('EarlyOutputSam3Facade', (EarlyOutputFilter, V5Sam3Facade), {})
    facade = facade_type(os.environ['SAM3_CHECKPOINT_PATH'])
    facade.serve(transport=args.transport, host=args.host, port=args.port,
        parent_watch=args.parent_watch)


if __name__ == '__main__':
    main()
