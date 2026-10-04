"""Original instance binding must retain the requested first-grasp staging."""

from types import SimpleNamespace

import pytest

from harness_v5_eval import _select_grasp_probe
from robots.libero.v5_state import Candidate


@pytest.mark.parametrize("mode", ["direct", "above_10cm", "yaw_90"])
def test_multiple_bowls_use_bound_instance_with_requested_mode(mode):
    entities = [SimpleNamespace(id=eid, name="bowl") for eid in ("e4", "e7")]
    choices = [Candidate("grasp", e.id, mode=m) for e in entities
               for m in ("direct", "above_10cm", "yaw_90")]
    action, count = _select_grasp_probe(
        choices, entities, "bowl", mode,
        lambda: Candidate("grasp", "e7", mode="direct"),
    )
    assert action == Candidate("grasp", "e7", mode=mode)
    assert count == 2


def test_missing_category_does_not_fall_back_to_another_object():
    entities = [SimpleNamespace(id="e4", name="bowl")]
    choices = [Candidate("grasp", "e4", mode="direct")]
    with pytest.raises(ValueError, match="category is not measured"):
        _select_grasp_probe(choices, entities, "moka pot", "direct", None)


def test_task_binding_cannot_select_a_different_category():
    entities = [SimpleNamespace(id=eid, name="bowl") for eid in ("e4", "e7")]
    choices = [Candidate("grasp", e.id, mode="yaw_90") for e in entities]
    with pytest.raises(ValueError, match="binder did not select"):
        _select_grasp_probe(choices, entities, "bowl", "yaw_90",
                            lambda: Candidate("articulate", "e8", mode="open"))


def test_unique_measured_category_needs_no_task_rebinding():
    entities = [SimpleNamespace(id="e7", name="moka pot")]
    action = Candidate("grasp", "e7", mode="above_10cm")
    assert _select_grasp_probe([action], entities, "moka pot", "above_10cm", None) == (action, 1)
