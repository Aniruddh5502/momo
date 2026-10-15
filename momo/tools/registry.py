"""ToolRegistry: all tools are registered once; specs select fixed subsets by name."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool

if TYPE_CHECKING:  # your existing persistent shell class
    PersistentShell = Any


@dataclass
class ToolContext:
    """Runtime context handed to tools at registration (no globals).

    The harness keeps `session_id` up to date when the active session changes.
    """
    project_root: Path
    session_id: str
    shell: "PersistentShell | None" = None
    subagent_manager: Any = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._tags: dict[str, set[str]] = {}

    def register(self, tool: BaseTool, *, tags: set[str] | None = None) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        self._tags[tool.name] = set(tags or ())

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Unknown tool '{name}'. Available: {', '.join(self._tools) or '(none)'}") from None

    def resolve(self, names: list[str]) -> list[BaseTool]:
        """Resolve names to tools, preserving the given order (order is part of the prompt prefix)."""
        return [self.get(n) for n in names]

    def tags(self, name: str) -> set[str]:
        return set(self._tags.get(name, set()))

    def names(self, tag: str | None = None) -> list[str]:
        if tag is None:
            return list(self._tools)
        return [n for n in self._tools if tag in self._tags[n]]


def register_all(registry: ToolRegistry, ctx: ToolContext) -> None:
    """Register every tool once at startup. Tools that need runtime context close over `ctx`."""
    from momo.tools.system_tools import create_system_tools
    for t in create_system_tools(ctx):
        registry.register(t, tags={"system"})

    from momo.tools.web_tools import create_web_tools
    for t in create_web_tools(ctx):
        registry.register(t, tags={"web"})

    from momo.tools.taskState import create_task_state_tools
    for t in create_task_state_tools(ctx):
        registry.register(t, tags={"harness"})

    if ctx.subagent_manager:
        from momo.tools.subagent.tools import create_subagent_tools
        for t in create_subagent_tools(ctx.subagent_manager):
            registry.register(t, tags={"orchestration"})