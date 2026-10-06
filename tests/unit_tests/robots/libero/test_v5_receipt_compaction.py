import copy
import json

from robots.libero.v5_state import compact_receipt, expand_receipt_metadata, receipt_lines, serialize


def test_duplicate_displacement_and_stop_are_compact_without_mutating_audit_receipt():
    receipt = {
        "tool": "articulate", "object": "e1", "verification": "unmeasured",
        "articulate_verified": None,
        "stop": "chunk_budget", "stop_condition": "chunk_budget",
        "measurement": {"gripper_m": [.08, .04], "held": [None, None],
            "dxyz_cm": {"e1": [0., 2.39, 0.]},
            "furniture": {"e1": {"dxyz_cm": [0., 2.39, 0.], "verified": None}}},
    }
    original = copy.deepcopy(receipt)
    compact = compact_receipt(receipt)
    assert receipt == original
    assert compact["measurement"]["dxyz_cm"] == {"e1": [0., 2.39, 0.]}
    assert compact["measurement"]["furniture"] == {"e1": {}}
    assert compact["articulate_verified"] is None
    assert compact["measurement"]["gripper_m"] == [.08, .04]
    assert compact["measurement"]["held"] == [None, None]
    assert compact["stop_condition"] == "chunk_budget" and "stop" not in compact
    rendered = serialize("open drawer", [], .04, None, [receipt] * 4)
    rows = [json.loads(line[8:]) for line in rendered.splitlines() if line.startswith("receipt ")]
    assert expand_receipt_metadata(rows) == [compact] * 3
    assert not any(line.startswith("receipt_defaults ") for line in rendered.splitlines())


def test_null_or_conflicting_furniture_verification_is_not_inferred_from_verification_text():
    receipt = {"verification": "unmeasured", "articulate_verified": None,
        "measurement": {"furniture": {"e1": {"verified": False}, "e2": {"verified": True}}}}
    assert compact_receipt(receipt) == receipt
    del receipt["articulate_verified"]
    assert compact_receipt(receipt) == receipt


def test_furniture_ids_and_all_original_measurement_values_are_recoverable():
    receipt = {"tool": "articulate", "object": "e0", "articulate_verified": None,
        "measurement": {"gripper_m": [.0795, .0792], "held": [None, None],
            "dxyz_cm": {"e1": [-2.41, -1.71, 1.17], "e2": [0., -.38, -.63]},
            "furniture": {"e1": {"dxyz_cm": [-2.41, -1.71, 1.17], "verified": None},
                "e2": {"dxyz_cm": [0., -.38, -.63], "verified": None}}}}
    compact = compact_receipt(receipt)
    reconstructed = copy.deepcopy(compact)
    for eid, evidence in reconstructed["measurement"]["furniture"].items():
        evidence["dxyz_cm"] = reconstructed["measurement"]["dxyz_cm"][eid]
        evidence["verified"] = reconstructed["articulate_verified"]
    assert reconstructed == receipt


def test_shared_metadata_is_explicit_and_restores_each_of_the_last_three_receipts():
    rows = [
        {"receipt_version": "measured_action/1", "tool": tool, "executed": True,
         "chunks": 80, "stop_condition": "chunk_budget", "verification": verification,
         "measurement": {"gripper_m": [.08, opening], "held": [None, None], "dxyz_cm": {}}}
        for tool, verification, opening in [("grasp", "failed", .04), ("articulate", "unmeasured", .08),
                                            ("vla_subtask", "verified", .03)]
    ]
    original = copy.deepcopy(rows)
    rendered = receipt_lines([{"tool": "discarded"}] + rows)
    assert len(rendered) == 3 and all(line.startswith("receipt ") for line in rendered)
    actual = [json.loads(line[8:]) for line in rendered]
    defaults = actual[0]["defaults"]
    assert defaults == {"receipt_version": "measured_action/1", "executed": True,
                        "chunks": 80, "stop_condition": "chunk_budget"}
    assert expand_receipt_metadata(actual) == original
    assert rows == original
    assert all("tool" in row and "verification" in row and "measurement" in row for row in actual)


def test_explicit_conflicting_metadata_overrides_shared_defaults_without_mutating_input():
    encoded = [{"defaults": {"chunks": 80, "receipt_version": "measured_action/1"}, "tool": "grasp"},
               {"tool": "vla_subtask", "chunks": 160, "receipt_version": "independent-version"}]
    original = copy.deepcopy(encoded)
    assert expand_receipt_metadata(encoded) == [
        {"tool": "grasp", "chunks": 80, "receipt_version": "measured_action/1"},
        {"tool": "vla_subtask", "chunks": 160, "receipt_version": "independent-version"},
    ]
    assert encoded == original


def test_one_receipt_and_different_or_missing_metadata_do_not_acquire_defaults():
    first = {"tool": "grasp", "chunks": 80, "executed": True}
    second = {"tool": "place", "chunks": 160}
    assert receipt_lines([first]) == ["receipt " + json.dumps(first, sort_keys=True, separators=(",", ":"))]
    lines = receipt_lines([first, second])
    assert all(line.startswith("receipt ") for line in lines)
    assert [json.loads(line[8:]) for line in lines] == [first, second]


def test_independent_measurements_and_stop_reasons_are_preserved():
    receipt = {"stop": "native_termination", "stop_condition": "held",
        "measurement": {"dxyz_cm": {"e1": [0., 3., 0.]},
            "furniture": {"e1": {"dxyz_cm": [0., 4., 0.], "verified": True},
                "e2": {"dxyz_cm": [1., 2., 3.], "verified": False}}}}
    assert compact_receipt(receipt) == receipt


def test_stove_endpoint_evidence_occurs_once_but_conflicting_evidence_is_retained():
    first = {"visible": True, "source_step": 2, "features": {"red_fraction": 0.}}
    second = {"visible": True, "source_step": 3, "features": {"red_fraction": .08}}
    receipt = {"object": "e1", "articulation_state": {"before": first, "after": second},
        "measurement": {"furniture": {"e1": {"state": "on", "verified": True,
            "before": copy.deepcopy(first), "after": copy.deepcopy(second)},
            "e2": {"before": first, "after": second}}}}
    compact = compact_receipt(receipt)
    assert compact["articulation_state"] == receipt["articulation_state"]
    assert compact["measurement"]["furniture"]["e1"] == {"state": "on", "verified": True}
    assert compact["measurement"]["furniture"]["e2"] == {"before": first, "after": second}
    receipt["measurement"]["furniture"]["e1"]["after"] = {"visible": False}
    assert compact_receipt(receipt)["measurement"]["furniture"]["e1"]["after"] == {"visible": False}
