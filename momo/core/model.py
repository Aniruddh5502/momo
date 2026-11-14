"""ModelFactory: builds OpenRouter chat models for specs.

One ChatOpenAI client is created per distinct model configuration and reused for every
turn, subagent call and summarizer. `bind_tools` is cheap, so tools are bound per call.
"""
from __future__ import annotations

import atexit
import json
import os
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from momo.core.spec import AgentSpec

load_dotenv()

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ModelFactory:
    def __init__(self, base_url: str = OPENROUTER_BASE_URL, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in the environment")
        self._clients: dict[tuple, ChatOpenAI] = {}
        atexit.register(self.close)

    def build(self, spec: AgentSpec, tools: list[BaseTool]) -> "Runnable":
        llm = self._client(spec)
        return llm.bind_tools(tools) if tools else llm

    def _client(self, spec: AgentSpec) -> ChatOpenAI:
        extra = spec.extra.get("openrouter", {})
        key = (spec.model, spec.temperature, json.dumps(extra, sort_keys=True, default=str))
        if key not in self._clients:
            self._clients[key] = ChatOpenAI(
                model=spec.model,          # OpenRouter slug, e.g. "qwen/qwen-2.5-72b-instruct"
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=spec.temperature,
                max_retries=2,
                **extra,
            )
        return self._clients[key]

    def close(self) -> None:
        """Close the HTTP connections held by every cached client. Safe to call twice."""
        for llm in self._clients.values():
            _close_quietly(getattr(llm, "root_client", None))
        self._clients.clear()


def _close_quietly(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass