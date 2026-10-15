"""The call_subagent tool the main agent uses to delegate work."""
from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from momo.tools.subagent.manager import SubagentManager


def create_subagent_tools(manager: SubagentManager) -> list[BaseTool]:
    @tool
    def call_subagent(name: str, prompt: str, new_chat: bool = False) -> str:
        """Delegate a task to a named subagent defined in .momo/agents/<name>.md.
        Continues that subagent's previous conversation unless new_chat is true.

        Args:
            name: subagent name, e.g. 'reviewer'.
            prompt: the exact instruction for the subagent.
            new_chat: start a fresh conversation instead of continuing the last one.
        """
        main_id = manager.get_active_session_id()
        if not main_id:
            return "Error: no active session to link the subagent to."
        return manager.run_subagent(name=name, prompt=prompt, main_session_id=main_id, new_chat=new_chat)

    return [call_subagent]