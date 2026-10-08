import contextvars
import json
import time
import uuid
from typing import Literal

from langchain_core.messages import (
    AIMessage, HumanMessage, ToolMessage,
)
from langchain_core.tools import tool
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding

import ui.animation as animation
from ui.animation import ThinkingAnimation
from momobot.core.engine import MomobotAgent
from momobot.core.state import AgentState

console = Console()

theme_char = "✽"
book_cloth = "#CC785C"
error      = "#BF4D43"
focus      = "#61AAF2"

SUBAGENT_CONFIG = {
    "base_url": "http://localhost:11434",
    "context": 50000,
    "recent_window": 6,
}

# True only while code is running inside a sub-agent (blocks recursive delegation).
_in_subagent: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "momobot_in_subagent", default=False
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _text(content) -> str:
    """Normalize message content (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content or "")


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _fmt_call(tc: dict) -> str:
    """shell(command='date')"""
    args = tc.get("args") or {}
    arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{tc.get('name', 'tool')}({_clip(arg_str, 90)})"


def _fmt_result(msg: ToolMessage) -> str:
    """One-line live summary of a tool result (mirrors the main CLI style)."""
    name = getattr(msg, "name", None) or "tool"
    content = _text(msg.content)
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = None

    if isinstance(parsed, dict) and "status" in parsed:
        status = parsed.get("status", "success")
        marker = {"success": "✓", "warning": "!", "error": "✗"}.get(status, "·")
        color  = {"success": focus, "warning": "yellow", "error": error}.get(status, "dim")
        meta   = parsed.get("metadata") or {}
        detail = meta.get("state_delta") or parsed.get("error_message") or ""
    else:
        marker, color, detail = "·", "dim", content

    line = f"[dim]{escape(name)}[/dim]  [{color}]{marker}[/{color}]"
    if detail:
        line += f"  [dim]{escape(_clip(detail, 100))}[/dim]"
    return line


# ----------------------------------------------------------------------
# Sub-agent runner (live output)
# ----------------------------------------------------------------------
def _run_subagent(agent_type: str, prompt: str) -> dict:
    """
    Runs the sub-agent to completion, printing each event as it happens.

    Runs inside a fresh contextvars.Context (see delegate_to_subagent) so the
    parent's LangGraph stream callbacks are NOT attached to the sub-agent;
    the only output the user sees is what this function prints.
    """
    _in_subagent.set(True)

    spin = ThinkingAnimation()

    def emit(markup: str):
        """Stop spinner -> print a line -> resume spinner (no stdout clash)."""
        spin.stop()
        console.print(markup)
        spin.start()

    agent = MomobotAgent(config={**SUBAGENT_CONFIG, "active_persona": agent_type})
    state = AgentState(
        messages=[HumanMessage(content=prompt)],
        token_usages=0,
        summary="",
    )
    thread_id = f"subagent-{uuid.uuid4().hex[:8]}"   # unique per call

    # --- header ---
    console.print(
        f"{theme_char} [bold]{escape(agent_type)}[/bold] [dim]sub-agent started[/dim]"
    )
    console.print(f"  [dim]├ task:[/dim] [dim]{escape(_clip(prompt, 140))}[/dim]")

    final_state = None
    seen_calls: set = set()
    seen_results: set = set()

    spin.start()
    try:
        for mode, payload in agent.run(state, thread_id=thread_id):
            if mode == "values":
                final_state = payload
                continue
            if mode != "messages":
                continue

            chunk, meta = payload
            if (meta or {}).get("langgraph_node") == "compaction":
                continue

            if isinstance(chunk, ToolMessage):
                key = getattr(chunk, "tool_call_id", None) or id(chunk)
                if key in seen_results:
                    continue
                seen_results.add(key)
                emit(f"  [dim]├ [/dim]{_fmt_result(chunk)}")

            elif isinstance(chunk, AIMessage):          # AIMessageChunk subclasses it
                for tc in getattr(chunk, "tool_calls", None) or []:
                    if not tc.get("name"):
                        continue                         # partial streamed fragment
                    key = tc.get("id") or (tc["name"], str(tc.get("args")))
                    if key in seen_calls:
                        continue
                    seen_calls.add(key)
                    emit(f"  [dim]├ [/dim][dim]{escape(_fmt_call(tc))}[/dim]")
    finally:
        spin.stop()
        try:
            agent.conn.close()
        except Exception:
            pass

    messages = (final_state or {}).get("messages", [])

    tools_used: list = []
    for m in messages:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", None) or "tool"
            if name not in tools_used:
                tools_used.append(name)

    response = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not m.tool_calls:
            response = _text(m.content).strip()
            if response:
                break

    return {
        "response": response or "(sub-agent returned no text)",
        "tools_used": tools_used,
    }


# ----------------------------------------------------------------------
# The tool
# ----------------------------------------------------------------------
@tool
def delegate_to_subagent(
    agent_type: Literal["executor", "researcher", "critique"],
    prompt: str,
) -> str:
    """
    Delegates a complex sub-task to a specialized sub-agent.

    Args:
        agent_type: The type of specialized agent to use.
        prompt: The detailed instruction for the sub-agent.
    """
    started = time.perf_counter()

    def _elapsed() -> float:
        return round(time.perf_counter() - started, 2)

    if _in_subagent.get():
        return json.dumps({
            "status": "error",
            "agent": agent_type,
            "error_code": "NESTED_DELEGATION",
            "error_message": "Sub-agents cannot delegate to other sub-agents.",
            "elapsed_seconds": _elapsed(),
        })

    # Stop the CLI's spinner (the *active* instance) before we print anything.
    if animation.active_animation is not None:
        animation.active_animation.stop()

    try:
        result = contextvars.Context().run(_run_subagent, agent_type, prompt)

        # --- final block ---
        console.print(
            f"  [dim]└ done[/dim]  [{focus}]✓[/{focus}]  [dim]{_elapsed():.1f}s[/dim]"
        )
        console.print(Padding(f"[dim {focus}]Sub Agent: {agent_type}[/]\n[dim]{result["response"]}[/]", (0, 0, 0, 4)))
        console.print("")

        return json.dumps({
            "status": "success",
            "agent": agent_type,
            "response": result["response"],
            "tools_used": result["tools_used"],
            "elapsed_seconds": _elapsed(),
        }, ensure_ascii=False)

    except Exception as e:
        console.print(
            f"  [dim]└ failed[/dim]  [{error}]✗[/{error}]  [{error}]{escape(str(e))}[/{error}]\n"
        )
        return json.dumps({
            "status": "error",
            "agent": agent_type,
            "error_code": "SUBAGENT_FAILED",
            "error_message": str(e),
            "elapsed_seconds": _elapsed(),
        }, ensure_ascii=False)