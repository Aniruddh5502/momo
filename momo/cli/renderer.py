"""Renderer: turns Events into terminal output. The same `render` serves live and replay.

Live mode skips the USER_MESSAGE echo (the user just typed it at the prompt);
replay prints it so a resumed session reads the same as the original.

Events from a subagent (event.agent set) are drawn in that subagent's color, taken from
its `color` frontmatter key. Unknown or missing colors fall back to a stable palette.
"""
from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.rule import Rule
from rich.text import Text

from momo.core.events import Event

MAX_RESULT_LINES = 10
MAX_ARG_CHARS = 100

# Used when a subagent doesn't set `color:`. Picked by hashing the name, so the same
# subagent gets the same color every session.
FALLBACK_PALETTE = ["cyan", "magenta", "bright_blue", "bright_green", "bright_yellow", "bright_red", "bright_magenta"]


class Renderer:
    def __init__(self, console: Console | None = None, agent_colors: dict[str, str] | None = None) -> None:
        self.console = console or Console()
        self.agent_colors: dict[str, str] = dict(agent_colors or {})
        self._last_usage: dict | None = None

    # ------------------------------------------------------------------ public API
    def register_agent_color(self, agent: str, color: str) -> None:
        self.agent_colors[agent] = color

    def render(self, event: Event, live: bool = True) -> None:
        handler = getattr(self, f"_on_{event.type.value}", None)
        if handler is not None:
            handler(event, live)

    def render_replay(self, events: Iterable[Event]) -> None:
        for event in events:
            self.render(event, live=False)

    def info(self, text: str, style: str = "dim") -> None:
        """Non-persisted notices (command output, hints)."""
        self.console.print(Text(text, style=style))

    # ------------------------------------------------------------------ colors
    
    def _color(self, event: Event, default: str = "") -> str:
        """Style for this event: the subagent's color if it has one, otherwise `default`."""
        if not event.agent:
            return default
        return self.agent_colors.get(event.agent) or self._fallback(event.agent)

    @staticmethod
    def _fallback(agent: str) -> str:
        return FALLBACK_PALETTE[sum(map(ord, agent)) % len(FALLBACK_PALETTE)]

    def _tag(self, event: Event) -> Text | None:
        """A small '[name]' label in front of subagent output, so it's clear who is speaking."""
        if not event.agent:
            return None
        return Text(f"[{event.agent}] ", style=f"bold {self._color(event)}")

    # ------------------------------------------------------------------ handlers
    def _on_user_message(self, e: Event, live: bool) -> None:
        if not live and not e.agent:
            self.console.print(Text.assemble(("› ", "bold cyan"), e.payload.get("text", "")))
            self.console.print("")

    def _on_assistant_text(self, e: Event, live: bool) -> None:
        color = self._color(e)
        tag = self._tag(e)
        if tag:
            self.console.print("\n", end="")
            self.console.print(Text.assemble(tag, ("⬤  ", color)))
        else:
            self.console.print("\n⬤ ", end="")
        self.console.print(Markdown(e.payload.get("text", ""), style=color) if color else Markdown(e.payload.get("text", "")))

    def _on_assistant_think(self, e: Event, live: bool) -> None:
        style = f"dim italic {self._color(e)}".strip()
        self.console.print(Text(e.payload.get("text", ""), style=style))

    def _on_tool_call(self, e: Event, live: bool) -> None:
        color = self._color(e)
        args = ", ".join(f"{k}={v!r}" for k, v in (e.payload.get("args") or {}).items())
        if len(args) > MAX_ARG_CHARS:
            args = args[: MAX_ARG_CHARS - 1] + "…"
        parts: list = []
        tag = self._tag(e)
        if tag:
            parts.append(tag)
        parts += [("✽ ", color or "green"), (e.payload.get("name", "?"), f"bold {color}".strip()), (f"     {args}", "dim")]
        self.console.print(Text.assemble(*parts))

    def _on_tool_result(self, e: Event, live: bool) -> None:
        if e.payload.get("hidden"):
            return                       # subagent output is already shown as its own events
        color = self._color(e)
        if e.payload.get("is_error"):
            style = "red"
        else:
            style = f"dim {color}".strip() if color else "dim"
        lines = (e.payload.get("content") or "").splitlines() or ["(no output)"]
        shown = lines[:MAX_RESULT_LINES]
        for i, line in enumerate(shown):
            prefix = "  └─ " if i == 0 else "    "
            self.console.print(Text(prefix + line, style=style), overflow="ellipsis", no_wrap=True)
        hidden = len(lines) - len(shown)
        if hidden > 0 or e.payload.get("truncated"):
            extra = f"… +{hidden} lines" if hidden > 0 else "… output truncated"
            self.console.print(Text("    " + extra, style=style))
        self.console.print("")

    def _on_compaction(self, e: Event, live: bool) -> None:
        p = e.payload
        self.console.print(Rule(
            f"context compacted: {p.get('tokens_before', 0):,} → {p.get('tokens_after', 0):,} tokens "
            f"({p.get('dropped', 0)} messages summarized)",
            style="magenta",
        ))

    def _on_usage(self, e: Event, live: bool) -> None:
        if e.agent:
            return                       # subagent usage would overwrite the main agent's ctx line
        self._last_usage = e.payload

    def _on_error(self, e: Event, live: bool) -> None:
        style = "yellow" if e.payload.get("recoverable") else "bold red"
        tag = self._tag(e)
        parts = [tag] if tag else []
        parts.append(Text(f"! {e.payload.get('message', 'error')}", style=style))
        self.console.print(Text.assemble(*parts))

    def _on_turn_end(self, e: Event, live: bool) -> None:
        if self._last_usage and not e.agent:
            u = self._last_usage
            tokens = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
            self.console.print(Text(f"  ctx {tokens:,} tokens ({u.get('usage_percent', 0):.0f}%)", style="dim"))
        if not e.agent:
            self._last_usage = None
            self.console.print()