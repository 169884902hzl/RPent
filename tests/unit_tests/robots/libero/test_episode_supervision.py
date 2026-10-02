from types import SimpleNamespace

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, RetryPromptPart
from pydantic_ai.models.function import FunctionModel

from robots.libero.episode_supervision import SupervisedLiberoToolkit
from rpent.dashboard.events import NullDashboardEventSink
from rpent.planner.api_loop import ApiAgentLoop
from rpent.tools.toolkit import ToolResult


class SupervisedFake:
    episode_supervision = True
    state = None
    prepare_episode_tools = SupervisedLiberoToolkit.prepare_episode_tools
    validate_episode_output = SupervisedLiberoToolkit.validate_episode_output
    _episode_finish = SupervisedLiberoToolkit._episode_finish

    def __init__(self):
        self.rejected_finish_attempts = 0
        self.ask_help_attempts = 0
        self.complete = False

    def solved(self):
        return self.complete

    def get_tools_spec(self):
        return [{"name": name, "description": name,
                 "input_schema": {"type": "object", "properties": {}}}
                for name in ("finish", "move")]

    def execute_tool(self, name, args):
        if name == "finish":
            return ToolResult(name, self._episode_finish())
        self.complete = True
        return ToolResult(name, {"terminated": True})


def test_finish_removed_after_two_refusals_and_success_stops():
    toolkit = SupervisedFake()
    actual_schemas = []
    def model(messages, info):
        names = [tool.name for tool in info.function_tools]
        actual_schemas.append(names)
        tool = "finish" if len(actual_schemas) <= 2 else "move"
        return ModelResponse(parts=[ToolCallPart(tool, {}, str(len(actual_schemas)))])
    result = ApiAgentLoop(FunctionModel(model), dashboard_events=NullDashboardEventSink()).solve(
        system_prompt="original prompt", user_message="task", toolkit=toolkit, max_turns=8)
    assert result.error is None
    assert toolkit.complete and toolkit.rejected_finish_attempts == 2
    assert "finish" in actual_schemas[0] and "finish" in actual_schemas[1]
    assert "finish" not in actual_schemas[2]
    assert len(actual_schemas) == 3
    assert result.finish_result is None


def test_unsolved_text_gets_validator_receipt_without_user_injection():
    toolkit = SupervisedFake()
    histories = []
    def model(messages, info):
        histories.append(messages)
        if len(histories) == 1:
            return ModelResponse(parts=[TextPart("I am done.")])
        assert any(isinstance(p, RetryPromptPart) and "环境报告任务未完成" in str(p.content)
                   for message in messages for p in message.parts)
        return ModelResponse(parts=[ToolCallPart("move", {}, "move")])
    result = ApiAgentLoop(FunctionModel(model), dashboard_events=NullDashboardEventSink()).solve(
        system_prompt="original prompt", user_message="task", toolkit=toolkit, max_turns=8)
    assert result.error is None and toolkit.solved()
    assert len(histories) == 2
    assert [m for m in result.messages if m["role"] == "user"] == [{"role": "user", "content": "task"}]


def test_unproductive_text_stops_at_the_registered_budget():
    toolkit = SupervisedFake()
    result = ApiAgentLoop(FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("done")])),
        dashboard_events=NullDashboardEventSink()).solve(system_prompt="original", user_message="task",
                                                       toolkit=toolkit, max_turns=3)
    assert not toolkit.solved()
    assert result.stats["turns_used"] == 3
