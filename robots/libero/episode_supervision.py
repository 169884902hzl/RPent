# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Opt-in common episode supervision, independent of the original prompts."""

from robots.libero.toolkit import LiberoToolkit
from rpent.tools.toolkit import readonly


class SupervisedLiberoToolkit(LiberoToolkit):
    """Keep an unsolved episode alive without resetting or fabricating actions."""

    episode_supervision = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rejected_finish_attempts = 0
        self.ask_help_attempts = 0
        spec, _ = self._tools["finish"]
        self.add_tool("finish", spec, self._episode_finish)

    @readonly
    def _episode_finish(self, **kwargs):
        if self.solved():
            return {"_finish": True, **kwargs}
        self.rejected_finish_attempts += 1
        if kwargs.get("status") in {"help", "ask_help"}:
            self.ask_help_attempts += 1
        return {"error": "finish refused", "terminated": False,
                "message": "环境报告任务未完成",
                "rejected_finish_attempts": self.rejected_finish_attempts}

    def prepare_episode_tools(self, ctx, tool_defs):
        """Remove finish from the next actual request after two refusals."""
        if self.rejected_finish_attempts < 2:
            return tool_defs
        return [definition for definition in tool_defs if definition.name != "finish"]

    def validate_episode_output(self, ctx, output):
        if self.solved():
            return output
        from pydantic_ai import ModelRetry
        # A validator receipt is logged by pydantic-ai; no synthetic user turn.
        raise ModelRetry("环境报告任务未完成")
