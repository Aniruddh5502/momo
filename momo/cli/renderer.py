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

    # ------------------------------------------------------------------ tool calls
    # Two kinds of event reach these handlers:
    #   SUBAGENT_START: sent when the model starts a call_subagent call (before it runs).
    #   TOOL_CALL:      sent once per call, after its result exists. It carries the
    #                   name, args, and result together.

    def _on_subagent_start(self, e: Event, live: bool) -> None:
        # A subagent runs for a long time, so print its header now, not when it finishes.
        self._print_tool_header(e)

    def _on_tool_call(self, e: Event, live: bool) -> None:
        # The live and replay paths both come here; `live` is not needed for tool calls.
        self._render_tool_call(e)

    def _render_tool_call(self, e: Event) -> None:
        """One block per tool call: a header line (name + args), then its output."""
        # The header was already printed by _on_subagent_start for subagent calls.
        # For every other call, header_shown is False, so print the header here.
        if not e.payload.get("header_shown"):
            self._print_tool_header(e)
        # hidden is True for a successful subagent call: its output is already printed
        # as the subagent's own events, so skip it here. Errors are never hidden.
        if not e.payload.get("hidden"):
            self._print_tool_output(e)

    def _print_tool_header(self, e: Event) -> None:
        # The tool name, for example "read_file".
        name = e.payload.get("name", "?")
        # The color for this event: the subagent's color, or "" for the main agent.
        color = self._color(e)
        # The args as one short string, formatted for this tool.
        args_str = self._format_args(name, e.payload.get("args") or {})
        # Text.assemble needs a list of pieces; each piece is (text, style).
        parts: list = []
        # For a subagent, put "[name] " in front so you can see who made the call.
        tag = self._tag(e)
        if tag:
            parts.append(tag)
        # The "✽ " marker, the bold tool name, then the args in dim text.
        parts += [("✽ ", color or "white"), (name, f"bold {color}".strip()), (f"     {args_str}", "dim")]
        # Print the whole line on one console line.
        self.console.print(Text.assemble(*parts))

    def _format_args(self, name: str, raw_args: dict) -> str:
        """Header text for a tool call. Add a branch here for a tool that needs its own format."""
        # Special case: task_init gets a short summary instead of the full task list.
        if name == "task_init" and isinstance(raw_args.get("tasks"), list):
            tasks = raw_args["tasks"]
            # Collect the name of each task (skip anything that is not a dict).
            names = []
            for t in tasks:
                if isinstance(t, dict):
                    names.append(t.get("name", "?"))
            # For example: "4 task(s): a, b, c"
            args_str = str(len(tasks)) + " task(s): " + ", ".join(names[:3])
            # More than 3 names: add "…" to show the list was cut short.
            if len(names) > 3:
                args_str += "…"
        else:
            # Default: key=value pairs, for example: path='a.py', limit=10
            parts = []
            for k, v in raw_args.items():
                # repr(v) puts quotes around strings, so the value is shown exactly.
                parts.append(k + " " + str(v))
            args_str = " ".join(parts)
        # Keep the header to one line: cut it at MAX_ARG_CHARS and add "…".
        if len(args_str) > MAX_ARG_CHARS:
            args_str = args_str[:MAX_ARG_CHARS - 1] + "…"
        return args_str

    def _print_tool_output(self, e: Event) -> None:
        # The same color as the header, dimmed, so output looks attached to the call.
        color = self._color(e)
        # An error is always red. Normal output uses the dim color.
        if e.payload.get("is_error"):
            style = "red"
        else:
            style = f"dim {color}".strip() if color else "dim"
        # Split the output into lines. An empty output becomes one line saying so.
        lines = (e.payload.get("content") or "").splitlines() or ["(no output)"]
        # Show only the first MAX_RESULT_LINES lines.
        shown = lines[:MAX_RESULT_LINES]
        for i, line in enumerate(shown):
            # The first line is indented by 2 spaces, the rest by 4.
            prefix = "  " if i == 0 else "    "
            # no_wrap + ellipsis: a long line is cut at the terminal edge with "…".
            self.console.print(Text(prefix + line, style=style), overflow="ellipsis", no_wrap=True)
        # How many lines were left out of the display.
        hidden = len(lines) - len(shown)
        # Say so if lines were left out, or if the stored content was cut to DISPLAY_MAX_CHARS.
        if hidden > 0 or e.payload.get("truncated"):
            extra = f"… +{hidden} lines" if hidden > 0 else "… output truncated"
            self.console.print(Text("    " + extra, style=style))
        # A blank line after each call's output, to separate it from the next one.
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