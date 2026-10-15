"""AgentSpec: an agent as plain data.

The main agent and every subagent are the same `Agent` class with different specs.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass(frozen=True)
class AgentSpec:
    name: str                          # "main", "researcher", ...
    model: str                         # Ollama model tag
    num_ctx: int
    prompt_sections: list[str]         # ordered section names for PromptBuilder
    tools: list[str]                   # tool names, resolved via ToolRegistry
    max_context_tokens: int            # compaction threshold
    keep_recent_messages: int = 6      # preserved verbatim after compaction
    max_iterations: int = 100          # hard cap on reasoning loops per turn
    temperature: float = 0.2
    extra: dict = field(default_factory=dict)   # future: permissions, hooks, ollama kwargs

    # -- (de)serialization: sessions snapshot their spec as JSON -------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSpec":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_json(cls, raw: str) -> "AgentSpec":
        return cls.from_dict(json.loads(raw))
