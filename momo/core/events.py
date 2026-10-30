"""Events are the unit of both persistence and rendering.

Every event carries everything the renderer needs, so replaying a stored
session never has to re-derive anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_TEXT = "assistant_text"      # emitted once per completed model message
    ASSISTANT_THINK = "assistant_think"    # optional reasoning content
    SUBAGENT_START = "subagent_start"      # call_id, name, args: printed when a subagent call begins
    TOOL_CALL = "tool_call"                # one per call: call_id, name, args, content, truncated, full_length, is_error, hidden
    COMPACTION = "compaction"              # summary, tokens_before, tokens_after, dropped
    USAGE = "usage"                        # prompt_tokens, completion_tokens, usage_percent
    ERROR = "error"                        # message, recoverable
    TURN_END = "turn_end"
    

@dataclass
class Event:
    type: EventType
    payload: dict[str, Any]
    session_id: str = ""
    seq: int = 0          # assigned by the store
    ts: float = 0.0       # assigned by the store
    agent:str = ""                         # To understand which agent it is