"""Agent: compiles a LangGraph for a spec and runs one user turn, yielding Events.

Graph topology (fixed):

    START -> COMPACT -> REASONING --(tool calls)--> TOOL_NODE -> COMPACT -> REASONING ...
                            |  \\--(malformed call, retry)--> REASONING
                            \\--(done / stopped)--> END

COMPACT passes through when under the threshold, so the topology never changes.
The agent knows nothing about the DB or the terminal: it yields Events and the
harness persists and renders them.
"""
from __future__ import annotations

import json
from typing import Callable, Iterator, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from momo.core.compactor import Compactor, estimate_tokens, message_text
from momo.core.events import Event, EventType
from momo.core.spec import AgentSpec

MAX_MALFORMED = 3            # consecutive malformed tool calls before the turn is ended
DISPLAY_MAX_CHARS = 4000     # tool output kept in the render event (full text stays in the message)
SUBAGENT_TOOL_NAME = "call_subagent"   # its result is shown as the subagent's own events instead


class AgentState(TypedDict):
    # Overwrite semantics: every node returns the complete new message list. This keeps
    # compaction (which rewrites history) trivial and order-safe.
    messages: list[BaseMessage]
    iterations: int
    malformed: int                 # consecutive malformed tool-call rounds
    retry: bool                    # reasoning asked for an immediate retry
    stop_reason: str | None
    compaction: dict | None        # set only by a COMPACT node that compacted


def repair_dangling_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Add placeholder ToolMessages for tool calls that never got a reply.

    Needed after an interrupted turn so the stored history stays valid for the model.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    repaired: list[BaseMessage] = []
    for m in messages:
        repaired.append(m)
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                call_id = call.get("id") or ""
                if call_id not in answered:
                    repaired.append(
                        ToolMessage(
                            content="Tool call was interrupted before it produced a result.",
                            tool_call_id=call_id,
                            name=call.get("name"),
                            status="error",
                        )
                    )
                    answered.add(call_id)
    return repaired


class Agent:
    def __init__(
        self,
        spec: AgentSpec,
        system_prompt: str,
        tools: list[BaseTool],
        model: Runnable,
        compactor: Compactor,
        on_progress: Callable[[int], None] | None = None,
    ) -> None:
        # on_progress(delta): called from the streaming thread with newly generated token
        # counts (a final correction uses Ollama's exact eval_count). The agent stays
        # UI-free: whoever wires the callback decides what to do with it.
        self.on_progress = on_progress
        self.spec = spec
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.compactor = compactor
        self._tool_map = {t.name: t for t in tools}
        self._messages: list[BaseMessage] = []
        self._graph = None
        # tokens that are always in the prompt: system prompt + tool schemas
        schema_chars = sum(len(t.description or "") + len(json.dumps(t.args, default=str)) for t in tools)
        self.compactor.tracker.baseline = estimate_tokens(system_prompt) + int(schema_chars / 3.5)

    # ------------------------------------------------------------------ public API
    @property
    def messages(self) -> list[BaseMessage]:
        return self._messages

    def compile(self) -> None:
        g = StateGraph(AgentState)
        g.add_node("compact", self._compact_node)
        g.add_node("reasoning", self._reasoning_node)
        g.add_node("tool_node", self._tool_node)
        g.add_edge(START, "compact")
        g.add_edge("compact", "reasoning")
        g.add_conditional_edges(
            "reasoning",
            self._route,
            {"tools": "tool_node", "retry": "reasoning", "end": END},
        )
        g.add_edge("tool_node", "compact")
        self._graph = g.compile()

    def run(self, messages: list[BaseMessage], user_input: str) -> Iterator[Event]:
        """Append the user message, stream the graph, yield Events.
        The final message list is available afterwards via `self.messages`."""
        if self._graph is None:
            self.compile()
        self._messages = list(messages) + [HumanMessage(content=user_input)]
        yield self._stamp(Event(EventType.USER_MESSAGE, {"text": user_input}))

        state: AgentState = {
            "messages": self._messages,
            "iterations": 0,
            "malformed": 0,
            "retry": False,
            "stop_reason": None,
            "compaction": None,
        }
        for chunk in self._graph.stream(state, stream_mode="updates"):
            for node, update in chunk.items():
                if not update:
                    continue
                previous_len = len(self._messages)
                if "messages" in update:
                    self._messages = update["messages"]
                for event in self._events_for(node, update, previous_len):
                    yield self._stamp(event)
        yield self._stamp(Event(EventType.TURN_END, {}))

    def _stamp(self, event: Event) -> Event:
        event.agent = self.spec.name if self.spec.name != "main" else ""
        return event

    # ------------------------------------------------------------------ graph nodes
    def _compact_node(self, state: AgentState) -> dict | None:
        messages = state["messages"]
        if not self.compactor.tracker.needs_compaction(messages):
            return None
        result = self.compactor.compact(messages)
        if not result.compacted:
            return None
        return {
            "messages": result.messages,
            "compaction": {
                "summary": result.summary,
                "tokens_before": result.tokens_before,
                "tokens_after": result.tokens_after,
                # dropped_ids can be empty when messages have no id, so count the removed messages
                "dropped": len(messages) - len(result.messages) + 1,
            },
        }

    def _reasoning_node(self, state: AgentState) -> dict:
        if state["iterations"] >= self.spec.max_iterations:
            return {"stop_reason": "max_iterations"}
        if state["malformed"] >= MAX_MALFORMED:
            return {"stop_reason": "malformed_tool_calls"}

        ai = self._generate([SystemMessage(content=self.system_prompt)] + state["messages"])
        self.compactor.tracker.update_turn(
            getattr(ai, "response_metadata", None) or {},
            index=len(state["messages"]),       # where this AIMessage lands in the list
        )
        update: dict = {
            "messages": state["messages"] + [ai],
            "iterations": state["iterations"] + 1,
            "retry": False,
        }
        invalid = getattr(ai, "invalid_tool_calls", None)
        if not ai.tool_calls and invalid:
            details = "; ".join(f"{c.get('name')}: {c.get('error')}" for c in invalid)
            hint = HumanMessage(
                content=(
                    f"Your previous tool call could not be parsed ({details}). "
                    "Call the tool again with valid JSON arguments that match its schema."
                ),
                additional_kwargs={"momo_hint": True},
            )
            update["messages"] = update["messages"] + [hint]
            update["malformed"] = state["malformed"] + 1
            update["retry"] = True
        return update

    def _generate(self, messages: list[BaseMessage]) -> AIMessage:
        """Stream the model so progress can be reported, then return one complete AIMessage."""
        merged = None
        final_meta: dict = {}
        streamed = 0
        for chunk in self.model.stream(messages):
            merged = chunk if merged is None else merged + chunk
            meta = getattr(chunk, "response_metadata", None) or {}
            if "eval_count" in meta:               # only Ollama's final chunk carries the counts
                final_meta = dict(meta)
            if chunk.content or chunk.additional_kwargs.get("reasoning_content"):
                streamed += 1                      # Ollama streams roughly one token per chunk
                if self.on_progress:
                    self.on_progress(1)
        if merged is None:
            return AIMessage(content="")
        exact = int(final_meta.get("eval_count") or 0)
        if self.on_progress and exact:
            self.on_progress(exact - streamed)     # snap the counter to the exact number
        return AIMessage(
            content=merged.content,
            additional_kwargs=merged.additional_kwargs,
            response_metadata=final_meta or merged.response_metadata,
            tool_calls=merged.tool_calls,
            invalid_tool_calls=merged.invalid_tool_calls,
            usage_metadata=merged.usage_metadata,
            id=merged.id,
        )

    def _tool_node(self, state: AgentState) -> dict:
        messages = state["messages"]
        last = messages[-1]
        assert isinstance(last, AIMessage)
        results: list[ToolMessage] = []
        schema_errors = 0
        for call in last.tool_calls:
            name, call_id = call["name"], call.get("id") or ""
            tool = self._tool_map.get(name)
            if tool is None:
                schema_errors += 1
                results.append(self._error_message(
                    f"Unknown tool '{name}'. Available tools: {', '.join(self._tool_map) or '(none)'}.",
                    call_id, name))
                continue
            try:
                out = tool.invoke(call)
                if not isinstance(out, ToolMessage):
                    out = ToolMessage(content=str(out), tool_call_id=call_id, name=name)
                if not out.name:
                    out.name = name
                results.append(out)
            except ValidationError as exc:
                schema_errors += 1
                results.append(self._error_message(
                    f"Invalid arguments for tool '{name}': {exc}. Fix the arguments and call it again.",
                    call_id, name))
            except Exception as exc:  # tool crashed: report it to the model, keep the loop alive
                results.append(self._error_message(
                    f"Tool '{name}' failed with {type(exc).__name__}: {exc}", call_id, name))
        all_bad = bool(last.tool_calls) and schema_errors == len(last.tool_calls)
        return {
            "messages": messages + results,
            "malformed": state["malformed"] + 1 if all_bad else 0,
        }

    def _route(self, state: AgentState) -> str:
        if state.get("stop_reason"):
            return "end"
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        if state.get("retry"):
            return "retry"
        return "end"

    # ------------------------------------------------------------------ events
    @staticmethod
    def _error_message(content: str, call_id: str, name: str | None) -> ToolMessage:
        return ToolMessage(content=content, tool_call_id=call_id, name=name, status="error")

    def _events_for(self, node: str, update: dict, previous_len: int) -> Iterator[Event]:
        if node == "compact":
            info = update.get("compaction")
            if info:
                yield Event(EventType.COMPACTION, dict(info))
            return

        if node == "reasoning":
            if update.get("stop_reason"):
                reason = update["stop_reason"]
                yield Event(EventType.ERROR, {
                    "message": {
                        "max_iterations": f"Stopped: reached the iteration limit ({self.spec.max_iterations}).",
                        "malformed_tool_calls": f"Stopped: {MAX_MALFORMED} malformed tool calls in a row.",
                    }.get(reason, f"Stopped: {reason}"),
                    "recoverable": False,
                })
                return
            new = update["messages"][previous_len:]
            ai = next((m for m in new if isinstance(m, AIMessage)), None)
            if ai is not None:
                think = ai.additional_kwargs.get("reasoning_content")
                if think:
                    yield Event(EventType.ASSISTANT_THINK, {"text": str(think)})
                text = message_text(ai).strip()
                if text:
                    yield Event(EventType.ASSISTANT_TEXT, {"text": text})
                # TOOL_CALL events are emitted by the tool_node, once each call has its result.
                # A subagent call runs for a long time, so its header is shown when it starts.
                for call in ai.tool_calls:
                    if call["name"] == SUBAGENT_TOOL_NAME:
                        yield Event(EventType.SUBAGENT_START, {
                            "call_id": call.get("id") or "",
                            "name": call["name"],
                            "args": call.get("args", {}),
                        })
                meta = getattr(ai, "response_metadata", None) or {}
                tracker = self.compactor.tracker
                yield Event(EventType.USAGE, {
                    "prompt_tokens": int(meta.get("prompt_eval_count") or 0),
                    "completion_tokens": int(meta.get("eval_count") or 0),
                    "usage_percent": round(tracker.usage_percent(update["messages"]), 1),
                })
            if update.get("retry"):
                yield Event(EventType.ERROR, {
                    "message": "The model produced a malformed tool call; asking it to retry.",
                    "recoverable": True,
                })
            return

        if node == "tool_node":
            # One TOOL_CALL event per call: name, args and result together.
            # The args are on the AIMessage that made the calls, which comes before the results.
            ai_calls = []
            for m in update["messages"][:previous_len]:
                if isinstance(m, AIMessage):
                    ai_calls = m.tool_calls          # keep the last one

            args_by_id = {}
            for c in ai_calls:
                args_by_id[c.get("id") or ""] = c

            for m in update["messages"][previous_len:]:
                if not isinstance(m, ToolMessage):
                    continue
                call = args_by_id.get(m.tool_call_id, {})
                name = m.name or call.get("name") or ""
                text = message_text(m)
                is_error = m.status == "error"
                is_subagent = name == SUBAGENT_TOOL_NAME
                yield Event(EventType.TOOL_CALL, {
                    "call_id": m.tool_call_id,
                    "name": name,
                    "args": call.get("args", {}),
                    "content": text[:DISPLAY_MAX_CHARS],
                    "truncated": len(text) > DISPLAY_MAX_CHARS,
                    "full_length": len(text),
                    "is_error": is_error,
                    # A subagent's header was printed when it started, and its output is
                    # already shown as its own events. Only its error text is printed here.
                    "header_shown": is_subagent,
                    "hidden": is_subagent and not is_error,
                })