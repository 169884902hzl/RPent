# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Moka-only SAM query ladder over one public image/depth capture.

The caller still associates neutral IDs, excludes the same pan mask when using
the returned raw instances, and fuses views. This helper has no runtime switch,
state-renderer fields, simulator queries, or completion/grasp labels.
"""

from collections import Counter

import numpy as np

from robots.libero.v5_perception_geometry import measured_points
from rpent.robots.components.sam3_client import Sam3Client


MOKA_QUERY_LADDER = (
    ("silver moka coffee pot", .5),
    ("silver octagonal coffee maker", .35),
    ("coffee pot", .25),
)


def collect_moka_instances(rpc, image_encoded, world, *, excluded_pan_mask=None,
                           record=None):
    """Return the first query's depth/geometry-usable original SAM items.

    Each returned item is a shallow copy with ``geometry_query`` and
    ``moka_query`` provenance. Its original encoded mask and other raw fields
    are preserved. ``query_count`` counts actual RPC requests. ``record(event)``
    gets query_started/query_finished and per-instance events; only instance
    events include copies of raw_mask and mask_after_pan_exclusion. A caller
    may count query_started events even if decoding later raises an error.

    Bounds use existing 02/98 percentiles. Existing rules require ten finite,
    nonzero depth points and reject low-score (<.5) extents >.45m or <=0.
    """
    world = np.asarray(world)
    if world.ndim != 3 or world.shape[2] != 3:
        raise ValueError("moka world must be a public HxWx3 point map")
    pan = None if excluded_pan_mask is None else np.asarray(excluded_pan_mask, dtype=bool)
    if pan is not None and pan.shape != world.shape[:2]:
        raise ValueError(f"moka pan-mask/world shape mismatch: {pan.shape} vs {world.shape[:2]}")
    trace = []
    for index, (query, minimum_score) in enumerate(MOKA_QUERY_LADDER):
        provenance = {"query": query, "minimum_score": minimum_score, "query_index": index}
        summary = {**provenance, "raw_instance_count": 0, "accepted_count": 0,
                   "rejection_counts": {}, "outcome": "request_started"}
        trace.append(summary)
        if record is not None:
            record({"event": "query_started", **provenance})
        reply = rpc.call("sam3.segment_all", kwargs={"image_base64": image_encoded,
            "text_prompt": query, "min_score": minimum_score}, timeout_s=120)
        accepted, rejected = [], Counter()
        instances = reply.get("instances", [])
        summary["raw_instance_count"] = len(instances)
        for instance_index, item in enumerate(instances):
            decoded = Sam3Client._decode_result(item)
            raw_mask = decoded.mask
            event = {"event": "instance", **provenance, "instance_index": instance_index,
                     "raw_item": item, "raw_mask": None, "mask_after_pan_exclusion": None,
                     "raw_finite_depth_points": 0, "finite_depth_points": 0,
                     "pan_pixels_removed": 0, "lower": None, "upper": None}
            if raw_mask is None:
                reason = "missing_mask"
            elif raw_mask.shape != world.shape[:2]:
                event.update(raw_mask=raw_mask.copy(), reason="mask_world_shape_mismatch")
                if record is not None:
                    record(event)
                raise ValueError(f"moka SAM-mask/world shape mismatch for {query!r}: "
                                 f"{raw_mask.shape} vs {world.shape[:2]}")
            else:
                mask = raw_mask.copy() if pan is None else raw_mask & ~pan
                points = measured_points(world, mask)
                original_points = measured_points(world, raw_mask)
                event.update(raw_mask=raw_mask.copy(), mask_after_pan_exclusion=mask.copy(),
                    raw_finite_depth_points=len(original_points), finite_depth_points=len(points),
                    pan_pixels_removed=int(raw_mask.sum() - mask.sum()))
                if len(points) < 10:
                    reason = "pan_exclusion" if len(original_points) >= 10 else "finite_depth_points_lt_10"
                else:
                    lower, upper = np.quantile(points, (.02, .98), axis=0)
                    event.update(lower=lower.tolist(), upper=upper.tolist())
                    score = float(item.get("score", 0.0))
                    extent = upper - lower
                    reason = "low_score_extent_invalid" if score < .5 and (
                        extent.max() > .45 or extent.min() <= 0) else "geometry_candidate"
                    if reason == "geometry_candidate":
                        accepted.append({**item, "geometry_query": query,
                                         "moka_query": provenance.copy()})
            event["reason"] = reason
            if reason != "geometry_candidate":
                rejected[reason] += 1
            if record is not None:
                record(event)
        summary.update(accepted_count=len(accepted), rejection_counts=dict(rejected),
            outcome="geometry_candidate" if accepted else "raw_empty" if not instances else "no_usable_geometry")
        if record is not None:
            record({"event": "query_finished", **summary})
        if accepted:
            return {"instances": accepted, "query_trace": trace, "query_count": len(trace)}
    return {"instances": [], "query_trace": trace, "query_count": len(trace)}
