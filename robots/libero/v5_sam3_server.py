"""Opt-in multi-instance SAM service; the frozen RPent SAM API is unchanged."""

from __future__ import annotations

import base64
import logging
import os

import numpy as np

from rpent.robots.components.sam3_server import (
    Sam3Facade,
    _build_argparser,
    _encode_mask_png,
)


class V5Sam3Facade(Sam3Facade):
    """Return distinct text-prompt masks using the existing SAM model/cache."""

    def _register_rpc(self) -> None:
        super()._register_rpc()
        self._rpc["sam3.segment_all"] = self.segment_all
        self._readonly_methods.add("sam3.segment_all")

    def segment_all(
        self, image_base64: str, text_prompt: str, min_score: float = 0.2
    ) -> dict:
        if not text_prompt.strip() or not 0 <= min_score <= 1:
            raise ValueError("invalid text prompt / confidence")
        image = base64.b64decode(image_base64, validate=True)
        with self._lock:
            state = self._state_for_image(image)
            with self._inference_context():
                output = self._processor.set_text_prompt(
                    prompt=text_prompt, state=state
                )
            masks, scores = output.get("masks"), output.get("scores")
            if masks is None or scores is None:
                return {"instances": []}
            masks = (
                masks.detach().float().cpu().numpy()
                if not isinstance(masks, np.ndarray)
                else masks
            )
            scores = (
                scores.detach().float().cpu().numpy()
                if not isinstance(scores, np.ndarray)
                else scores
            )
            masks = masks.reshape((-1, *masks.shape[-2:])) > 0
            scores = scores.reshape(-1)
            if len(masks) != len(scores):
                raise ValueError("SAM mask/score count mismatch")
            kept = []
            results = []
            # A package and the printed objects on its surface are nested
            # masks, not independent physical instances. Keep the larger mask.
            for idx in sorted(
                range(len(scores)), key=lambda i: (-int(masks[i].sum()), -scores[i])
            ):
                mask = masks[idx]
                if scores[idx] < min_score or not mask.any():
                    continue
                if any(
                    (mask & prior).sum() / max(1, min(mask.sum(), prior.sum())) > 0.85
                    for prior in kept
                ):
                    continue
                kept.append(mask)
                results.append(
                    {
                        "found": True,
                        "score": float(scores[idx]),
                        "mask_png_base64": _encode_mask_png(mask),
                        "mask_shape": list(mask.shape),
                    }
                )
            return {"instances": results}


def main() -> None:
    """Start the independent v5 segmentation service."""
    args = _build_argparser().parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.cuda_device is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.cuda_device)
    facade = V5Sam3Facade(os.environ["SAM3_CHECKPOINT_PATH"])
    facade.serve(
        transport=args.transport,
        host=args.host,
        port=args.port,
        parent_watch=args.parent_watch,
    )


if __name__ == "__main__":
    main()
