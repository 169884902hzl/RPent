"""Development pairing preserves native success and infrastructure failures."""

from scripts.summarize_v5_A3_step750_20261003 import paired


def test_pairing_uses_official_success_and_keeps_missing_and_startup_separate():
    def row(success, infrastructure=False):
        return {"official_success": success, "explicit_successful_finish": False,
                "infrastructure_failure": infrastructure}

    keys = [("spatial", n, 40) for n in range(5)]
    old = dict(zip(keys[:4], [row(True), row(False), row(True), row(False, True)]))
    new = dict(zip(keys, [row(True), row(True), row(False), row(False), row(True)]))
    result = paired(old, new)
    assert result["cells"] == {"both_success": 1, "gain": 1, "regression": 1, "infrastructure_pair": 1}
    assert result["valid_pairs"] == 3
    assert result["success_delta_pp"] == 0
    assert result["missing_left"] == [list(keys[4])]
