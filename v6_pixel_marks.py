# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public entity-ID painting, without projection or observation semantics.

Extracted from ``robots/libero/v6_som.py::render_marks`` in RPent's
``source_v6_frame434_20261004`` snapshot, SHA256
``b9061a7515604ca5a69990bdd5064c721e255d925a6b6713565ca811985169dc``.
The upstream copyright and Apache-2.0 designation are preserved above.

The caller supplies an already validated pixel box. This primitive does not
decide whether a box came from perception, an offline simulator, or a saved
annotation. Such provenance must remain explicit in the caller's manifest.
"""
from __future__ import annotations

from collections.abc import Sequence

from PIL import ImageDraw

VERSION = "public-id-pixel-mark/1"
UPSTREAM_SOURCE_SHA256 = "b9061a7515604ca5a69990bdd5064c721e255d925a6b6713565ca811985169dc"


def draw_pixel_mark(draw: ImageDraw.ImageDraw, box: Sequence[int], label: str) -> None:
    """Paint the RPent yellow outline and black-backed public ID label."""
    draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), outline=(255, 216, 0), width=3)
    x, y = box[:2]
    text_box = draw.textbbox((x, y), label)
    draw.rectangle(text_box, fill=(0, 0, 0))
    draw.text((x, y), label, fill=(255, 216, 0))
