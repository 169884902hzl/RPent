# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""The startup optimization preserves output cutoffs and other SAM RPCs."""

import threading
from types import SimpleNamespace

import pytest

from coordination.bounded_skills_20261016.scripts.sam3_output_filter_startup_20261020 import (
    EarlyOutputFilter,
)

torch = pytest.importorskip('torch')


class FakeFacade:
    def __init__(self, scores):
        self._processor = SimpleNamespace(confidence_threshold=0.)
        self._lock = threading.Lock()
        self.scores = scores

    def segment_all(self, image, text, min_score=.2):
        with self._lock:
            if text == 'invalid':
                raise ValueError('bad prompt')
            # This is the processor's real bfloat16 strict comparison,
            # followed by the existing facade's float CPU output cutoff.
            ids = torch.nonzero(self.scores > self._processor.confidence_threshold).flatten()
            return [(int(i), float(self.scores[i])) for i in ids
                if float(self.scores[i]) >= min_score]

    def segment(self):
        return {'score': .1, 'reason': 'top score below cutoff',
            'processor_cutoff': self._processor.confidence_threshold}


class FastFacade(EarlyOutputFilter, FakeFacade):
    pass


@pytest.mark.parametrize('minimum', [0., .1, .15, .2, .5, 1.])
@pytest.mark.parametrize('dtype', [torch.bfloat16, torch.float16, torch.float32])
def test_boundary_scores_and_instance_order_match_frozen_outputs(minimum, dtype):
    centre = torch.tensor(minimum, dtype=dtype)
    scores = torch.stack([torch.tensor(0., dtype=dtype),
        torch.nextafter(centre, torch.tensor(float('-inf'), dtype=dtype)), centre,
        torch.nextafter(centre, torch.tensor(float('inf'), dtype=dtype)),
        torch.tensor(1., dtype=dtype)])
    frozen, fast = FakeFacade(scores), FastFacade(scores)
    assert fast.segment_all('image', 'object', minimum) == frozen.segment_all('image', 'object', minimum)
    assert fast.segment() == frozen.segment()


def test_failure_restores_the_frozen_single_mask_behavior():
    facade = FastFacade(torch.tensor([.3]))
    with pytest.raises(ValueError, match='bad prompt'):
        facade.segment_all('image', 'invalid', .2)
    assert facade.segment()['processor_cutoff'] == 0.
