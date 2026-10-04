import copy

import pytest

from robots.libero.v6_text import instruction, replace_instruction


def test_instruction_corruption_preserves_all_other_visible_input_and_labels():
    row = {"request": {"state": 'instruction "move the bowl"\ne e7 name=bowl\nrobot held=e7',
                       "questions": {"action": {"criteria": {"C0": "finish()", "C1": "place(e7,e2,on)"}}}},
           "acceptable_actions": ["C1"], "label_evidence": {"physical_branch_checked": True},
           "media_pair": {"views": [{"path": "main.png"}, {"path": "wrist.png"}]}}
    saved = copy.deepcopy(row)
    changed = replace_instruction(row, "open the drawer")
    assert row == saved
    assert instruction(changed["request"]["state"]) == "open the drawer"
    assert changed["request"]["state"].partition("\n")[2] == row["request"]["state"].partition("\n")[2]
    assert changed["request"]["questions"] == row["request"]["questions"]
    for field in ("acceptable_actions", "label_evidence", "media_pair"):
        assert changed[field] == row[field]
    assert "corrupt" not in str(changed["request"])
    with pytest.raises(ValueError, match="different"):
        replace_instruction(row, "move the bowl")
