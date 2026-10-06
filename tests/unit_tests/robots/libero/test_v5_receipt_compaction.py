import copy
import json

from robots.libero.v5_state import compact_receipt, serialize


def test_duplicate_displacement_and_stop_are_compact_without_mutating_audit_receipt():
    receipt = {
        "tool": "articulate", "object": "e1", "verification": "unmeasured",
        "stop": "chunk_budget", "stop_condition": "chunk_budget",
        "measurement": {"gripper_m": [.08, .04], "held": [None, None],
            "dxyz_cm": {"e1": [0., 2.39, 0.]},
            "furniture": {"e1": {"dxyz_cm": [0., 2.39, 0.], "verified": None}}},
    }
    original = copy.deepcopy(receipt)
    compact = compact_receipt(receipt)
    assert receipt == original
    assert compact["measurement"]["dxyz_cm"] == {"e1": [0., 2.39, 0.]}
    assert compact["measurement"]["furniture"] == {"e1": {"verified": None}}
    assert compact["measurement"]["gripper_m"] == [.08, .04]
    assert compact["measurement"]["held"] == [None, None]
    assert compact["stop_condition"] == "chunk_budget" and "stop" not in compact
    rendered = serialize("open drawer", [], .04, None, [receipt] * 4)
    rows = [json.loads(line[8:]) for line in rendered.splitlines() if line.startswith("receipt ")]
    assert rows == [compact] * 3


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
