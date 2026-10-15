"""Context management: token tracking and compaction (summarize old messages)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable

CHARS_PER_TOKEN = 3.5
SUMMARY_FLAG = "momo_summary"
SUMMARY_HEADER = "[Summary of the earlier conversation]\n"

SUMMARY_PROMPT = """You compress an agent conversation so work can continue after older messages are dropped.
Write a dense summary covering: the user's goals and constraints; decisions made; files, commands and results that matter; what is done; what remains.
Keep exact names, paths, numbers and error messages. Omit pleasantries and raw tool output you can describe in a line.
If the transcript begins with an earlier summary, merge it into your new summary instead of repeating it.
Output only the summary."""

_MAX_TEXT_CHARS = 4000      # per message in the transcript sent to the summarizer
_MAX_TOOL_CHARS = 1500


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def message_text(msg: BaseMessage) -> str:
    """Flatten message content (str or list of blocks) to text."""
    content = msg.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def _message_tokens(msg: BaseMessage) -> int:
    n = estimate_tokens(message_text(msg))
    if isinstance(msg, AIMessage) and msg.tool_calls:
        n += estimate_tokens(json.dumps(msg.tool_calls, default=str))
    return n


@dataclass
class TokenTracker:
    """Knows how many tokens the next prompt will use.

    Two sources, in order of preference:
      1. Ollama's real count from the last model call (anchored to that AIMessage's index),
         plus an estimate for the messages appended after it (tool results, hints).
      2. Estimate of the whole history plus the fixed baseline (system prompt + tool
         schemas). Used at the start of a turn, after a resume, and after compaction.
    """
    max_context: int
    baseline: int = 0                 # system prompt + tool schemas, set by the Agent
    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    _anchor: int | None = None        # index of the AIMessage the real counts belong to

    def update_turn(self, response_metadata: dict, index: int | None = None) -> None:
        """Record Ollama's counts for the model call that produced messages[index]."""
        self.last_prompt_tokens = int(response_metadata.get("prompt_eval_count") or 0)
        self.last_completion_tokens = int(response_metadata.get("eval_count") or 0)
        self._anchor = index

    def estimate(self, messages: list[BaseMessage]) -> int:
        return sum(_message_tokens(m) for m in messages)

    def current_tokens(self, messages: list[BaseMessage]) -> int:
        a = self._anchor
        if a is not None and a < len(messages) and isinstance(messages[a], AIMessage):
            # prompt_eval_count already covers system prompt, tools and everything before the
            # anchor; eval_count is the anchor's own output; the rest is estimated.
            real = self.last_prompt_tokens + self.last_completion_tokens
            return real + self.estimate(messages[a + 1:])
        return self.baseline + self.estimate(messages)

    def usage_percent(self, messages: list[BaseMessage]) -> float:
        return 100.0 * self.current_tokens(messages) / self.max_context if self.max_context else 0.0

    def needs_compaction(self, messages: list[BaseMessage]) -> bool:
        return self.current_tokens(messages) > self.max_context

    def reset(self) -> None:
        """Forget real counts. Called after compaction, because the anchored message's
        counts described the old, longer prompt."""
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self._anchor = None


@dataclass
class CompactionResult:
    messages: list[BaseMessage]
    summary: str
    tokens_before: int
    tokens_after: int
    dropped_ids: list[str] = field(default_factory=list)   # ids of messages replaced by the summary
    compacted: bool = False            # True when history was actually rewritten (ids may be missing)


class Compactor:
    def __init__(self, summarizer: "Runnable", tracker: TokenTracker, keep_recent: int) -> None:
        self.summarizer = summarizer
        self.tracker = tracker
        self.keep_recent = keep_recent

    def compact(self, messages: list[BaseMessage]) -> CompactionResult:
        """Replace everything but the most recent messages with one summary message.

        The system prompt is not part of `messages` (it is rebuilt every prompt), so the
        result is: [summary] + recent. If there is nothing safe to compact, the messages
        come back unchanged with an empty `dropped_ids`.
        """
        before = self.tracker.current_tokens(messages)
        cut = self._find_cut(messages)
        if cut <= 0:
            return CompactionResult(messages, "", before, before, [], compacted=False)

        old, recent = messages[:cut], messages[cut:]
        summary = self._summarize(old)
        summary_msg = HumanMessage(
            content=SUMMARY_HEADER + summary,
            additional_kwargs={SUMMARY_FLAG: True},
        )
        new_messages = [summary_msg] + recent
        self.tracker.reset()
        after = self.tracker.current_tokens(new_messages)
        return CompactionResult(
            messages=new_messages,
            summary=summary,
            tokens_before=before,
            tokens_after=after,
            dropped_ids=[m.id for m in old if m.id],
            compacted=True,
        )

    # ------------------------------------------------------------------ internals
    def _find_cut(self, messages: list[BaseMessage]) -> int:
        """Index where 'recent' starts. Never leaves a ToolMessage first in 'recent',
        so an AI tool_call and its tool replies always stay on the same side."""
        n = len(messages)
        for keep in range(self.keep_recent, 0, -1):
            cut = n - keep
            while cut > 0 and isinstance(messages[cut], ToolMessage):
                cut -= 1
            if cut <= 0:
                continue
            if all(m.additional_kwargs.get(SUMMARY_FLAG) for m in messages[:cut]):
                continue    # only a previous summary would be re-summarized: pointless
            return cut
        return 0

    def _summarize(self, old: list[BaseMessage]) -> str:
        reply = self.summarizer.invoke(
            [
                SystemMessage(content=SUMMARY_PROMPT),
                HumanMessage(content=self._transcript(old)),
            ]
        )
        return message_text(reply).strip()

    @staticmethod
    def _transcript(messages: list[BaseMessage]) -> str:
        lines: list[str] = []
        for m in messages:
            text = message_text(m)
            if isinstance(m, ToolMessage):
                lines.append(f"[tool result: {m.name or '?'}] {text[:_MAX_TOOL_CHARS]}")
            elif isinstance(m, AIMessage):
                if text:
                    lines.append(f"[assistant] {text[:_MAX_TEXT_CHARS]}")
                for call in m.tool_calls:
                    args = json.dumps(call.get("args", {}), default=str)[:500]
                    lines.append(f"[assistant tool call] {call.get('name')}({args})")
            else:
                lines.append(f"[user] {text[:_MAX_TEXT_CHARS]}")
        return "\n".join(lines)
