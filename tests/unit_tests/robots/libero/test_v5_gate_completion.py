"""Keep native task completion separate from a planner finish selection."""

from scripts.summarize_v5_gate200_20261001 import correct_completion


def test_persistent_native_success_does_not_require_an_invented_finish():
    result = {"persist_attempts_v1": True, "official_success": True,
              "native_terminated": True, "correct_finish": False}
    assert correct_completion(result)
    assert result["correct_finish"] is False


def test_persistent_completion_requires_both_official_and_native_success():
    for official, native in ((False, False), (False, True), (True, False)):
        assert not correct_completion({"persist_attempts_v1": True,
                                       "official_success": official,
                                       "native_terminated": native,
                                       "correct_finish": True})


def test_legacy_explicit_finish_contract_remains_separate():
    assert correct_completion({"correct_finish": True})
    assert not correct_completion({"official_success": True, "native_terminated": True})
