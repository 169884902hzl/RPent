"""Moka fallback uses measured geometry and keeps original SAM payloads."""

import base64
import copy
import io

import imageio.v2 as imageio
import numpy as np
import pytest

from robots.libero.v5_moka_queries import MOKA_QUERY_LADDER, collect_moka_instances
from rpent.robots.components.sam3_client import Sam3Client


def item(mask, score=.7):
    buffer = io.BytesIO()
    imageio.imwrite(buffer, mask.astype(np.uint8) * 255, format="png")
    return {"found": True, "score": score, "mask_shape": list(mask.shape),
            "mask_png_base64": base64.b64encode(buffer.getvalue()).decode("ascii")}


def world_map(shape=(8, 8)):
    y, x = np.mgrid[:shape[0], :shape[1]]
    return np.stack((x * .01, y * .01, .9 + (x + y) * .001), axis=-1)


class RecordedRPC:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def call(self, method, *, kwargs, timeout_s):
        self.calls.append((method, kwargs, timeout_s))
        return next(self.replies)


def test_nonempty_reply_without_finite_depth_continues_to_synonym():
    world = world_map()
    invalid = np.zeros((8, 8), dtype=bool)
    invalid[:2] = True
    valid = ~invalid
    world[invalid] = np.nan
    rpc = RecordedRPC([{"instances": [item(invalid)]}, {"instances": [item(valid, .4)]}])
    result = collect_moka_instances(rpc, "public_image", world)
    assert result["query_count"] == 2
    assert result["query_trace"][0]["outcome"] == "no_usable_geometry"
    assert result["query_trace"][0]["rejection_counts"] == {"finite_depth_points_lt_10": 1}
    assert result["instances"][0]["geometry_query"] == MOKA_QUERY_LADDER[1][0]
    assert [call[1]["min_score"] for call in rpc.calls] == [.5, .35]


def test_pan_exclusion_controls_fallback_without_mutating_original_masks():
    pan = np.ones((8, 8), dtype=bool)
    pan[4:, 4:] = False
    pan_only = pan.copy()
    raw = item(pan_only)
    mixed = item(np.ones((8, 8), dtype=bool), .4)
    original = copy.deepcopy([raw, mixed])
    rpc = RecordedRPC([{"instances": [raw]}, {"instances": [mixed]}])
    events = []
    result = collect_moka_instances(rpc, "image", world_map(), excluded_pan_mask=pan, record=events.append)
    assert [raw, mixed] == original
    assert result["query_count"] == 2
    assert result["query_trace"][0]["rejection_counts"] == {"pan_exclusion": 1}
    kept = result["instances"][0]
    assert kept["mask_png_base64"] == mixed["mask_png_base64"]
    assert kept["moka_query"] == {"query": MOKA_QUERY_LADDER[1][0], "minimum_score": .35, "query_index": 1}
    instance_events = [event for event in events if event["event"] == "instance"]
    assert instance_events[0]["raw_finite_depth_points"] == 48
    assert instance_events[0]["finite_depth_points"] == 0
    assert instance_events[1]["raw_mask"].sum() == 64
    assert instance_events[1]["mask_after_pan_exclusion"].sum() == 16
    assert Sam3Client._decode_result(mixed).mask.sum() == 64


def test_low_score_background_extent_falls_back_to_coffee_pot():
    world = world_map((6, 6))
    world[..., 0] *= 12
    small = np.zeros((6, 6), dtype=bool)
    small[:, :3] = True
    rpc = RecordedRPC([{"instances": []}, {"instances": [item(~np.zeros((6, 6), dtype=bool), .4)]},
                       {"instances": [item(small, .3)]}])
    result = collect_moka_instances(rpc, "image", world)
    assert result["query_count"] == 3
    assert result["query_trace"][1]["rejection_counts"] == {"low_score_extent_invalid": 1}
    assert result["instances"][0]["geometry_query"] == "coffee pot"
    assert [(call[1]["text_prompt"], call[1]["min_score"]) for call in rpc.calls] == list(MOKA_QUERY_LADDER)


def test_depth_usable_pan_boundary_still_falls_back_under_existing_mask_fraction():
    pan = np.ones((20, 20), dtype=bool)
    pan[-2:] = False
    combined = item(np.ones((20, 20), dtype=bool))
    actual_pot = item(~pan)
    rpc = RecordedRPC([{"instances": [combined]}, {"instances": [actual_pot]}])
    result = collect_moka_instances(rpc, "image", world_map((20, 20)), excluded_pan_mask=pan)
    assert result["query_count"] == 2
    assert result["query_trace"][0]["rejection_counts"] == {"pan_exclusion_mask_fraction_lt_15pct": 1}
    assert result["instances"][0]["mask_png_base64"] == actual_pot["mask_png_base64"]


def test_low_score_flat_extent_is_rejected_without_a_new_height_prior():
    world = world_map()
    world[..., 2] = .9
    payload = item(np.ones((8, 8), dtype=bool), .4)
    rpc = RecordedRPC([{"instances": [payload]}] * 3)
    result = collect_moka_instances(rpc, "image", world)
    assert result["instances"] == []
    assert result["query_count"] == 3
    assert all(trace["rejection_counts"] == {"low_score_extent_invalid": 1} for trace in result["query_trace"])


def test_first_usable_query_returns_all_candidates_for_existing_association():
    first, second = item(np.ones((8, 8), dtype=bool)), item(np.ones((8, 8), dtype=bool), .6)
    rpc = RecordedRPC([{"instances": [first, second]}])
    result = collect_moka_instances(rpc, "image", world_map())
    assert result["query_count"] == 1
    assert len(result["instances"]) == 2
    assert all(row["geometry_query"] == MOKA_QUERY_LADDER[0][0] for row in result["instances"])
    assert "moka_query" not in first and "geometry_query" not in second


def test_missing_mask_and_zero_depth_are_unusable_not_raw_empty():
    missing = {"found": False, "score": .7, "reason": "not found"}
    rpc = RecordedRPC([{"instances": [missing]}, {"instances": [item(np.ones((8, 8), dtype=bool))]},
                       {"instances": []}])
    result = collect_moka_instances(rpc, "image", np.zeros((8, 8, 3)))
    assert [trace["outcome"] for trace in result["query_trace"]] == ["no_usable_geometry", "no_usable_geometry", "raw_empty"]
    assert result["query_trace"][0]["rejection_counts"] == {"missing_mask": 1}
    assert result["query_trace"][1]["rejection_counts"] == {"finite_depth_points_lt_10": 1}


def test_fresh_mask_shape_mismatch_is_an_explicit_error_and_is_recorded():
    rpc = RecordedRPC([{"instances": [item(np.ones((4, 4), dtype=bool))]}])
    events = []
    with pytest.raises(ValueError, match="SAM-mask/world shape mismatch"):
        collect_moka_instances(rpc, "image", world_map(), record=events.append)
    assert len(rpc.calls) == 1
    assert events[0]["event"] == "query_started"
    assert events[-1]["reason"] == "mask_world_shape_mismatch"
    assert events[-1]["raw_mask"].shape == (4, 4)


def test_pan_mask_shape_mismatch_does_not_start_a_query():
    rpc = RecordedRPC([])
    with pytest.raises(ValueError, match="pan-mask/world shape mismatch"):
        collect_moka_instances(rpc, "image", world_map(), excluded_pan_mask=np.ones((4, 4)))
    assert rpc.calls == []


def test_empty_queries_return_three_requests_and_auditable_outcomes():
    rpc = RecordedRPC([{"instances": []}] * 3)
    events = []
    result = collect_moka_instances(rpc, "image", world_map(), record=events.append)
    assert result["instances"] == []
    assert result["query_count"] == 3 == len(result["query_trace"])
    assert len([event for event in events if event["event"] == "query_started"]) == 3
    assert len([event for event in events if event["event"] == "query_finished"]) == 3
    assert all(trace["outcome"] == "raw_empty" for trace in result["query_trace"])


def test_mutating_audit_mask_copies_does_not_change_returned_payload():
    payload = item(np.ones((8, 8), dtype=bool))
    before = copy.deepcopy(payload)
    def record(event):
        if event["event"] == "instance":
            event["raw_mask"][:] = False
            event["mask_after_pan_exclusion"][:] = False
    result = collect_moka_instances(RecordedRPC([{"instances": [payload]}]), "image", world_map(), record=record)
    assert payload == before
    assert Sam3Client._decode_result(result["instances"][0]).mask.sum() == 64
