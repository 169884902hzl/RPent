from original_api_batch import classify_episode


def test_budget_exit_with_real_calls_is_not_a_launch_failure():
    transcript = {"error": "API planner timed out after 1200s",
                  "stats": {"turns_used": 53, "tool_calls": 53}}
    assert classify_episode(physical=False, exit_code=1, transcript=transcript,
                            budget={"max_turns": 100}) == "budget_exhausted"


def test_native_success_takes_precedence_over_stop_errors():
    assert classify_episode(physical=True, exit_code=1, transcript={"error": "timeout"},
                            budget={"max_turns": 100}) == "success"


def test_zero_call_provider_error_remains_infrastructure_failure():
    assert classify_episode(physical=False, exit_code=1, transcript={"stats": {}},
                            budget={"max_turns": 100}) == "infrastructure_error"
