"""ModelFactory: builds Ollama chat models for specs.

One ChatOllama client (and its HTTP connection pool) is created per distinct model
configuration and reused for every turn, subagent call and summarizer. Creating a new
client per turn leaked a socket each time, which Python then reports as a ResourceWarning.
`bind_tools` is cheap and opens no connection, so tools are bound per call on top of the
shared client.
"""
from __future__ import annotations

import atexit
import json
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from momo.core.spec import AgentSpec

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


class ModelFactory:
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url
        self._clients: dict[tuple, ChatOllama] = {}
        atexit.register(self.close)

    def build(self, spec: AgentSpec, tools: list[BaseTool]) -> "Runnable":
        """A model for `spec`, with `tools` bound. With no tools the plain model is returned
        (used for summarization). `num_ctx` is always passed explicitly: Ollama's default
        context is small and truncates silently."""
        llm = self._client(spec)
        return llm.bind_tools(tools) if tools else llm

    def _client(self, spec: AgentSpec) -> ChatOllama:
        extra = spec.extra.get("ollama", {})
        key = (spec.model, spec.num_ctx, spec.temperature, json.dumps(extra, sort_keys=True, default=str))
        if key not in self._clients:
            self._clients[key] = ChatOllama(
                model=spec.model,
                base_url=self.base_url,
                num_ctx=spec.num_ctx,
                temperature=spec.temperature,
                **extra,
            )
        return self._clients[key]

    def close(self) -> None:
        """Close the HTTP connections held by every cached client. Safe to call twice."""
        for llm in self._clients.values():
            _close_quietly(getattr(llm, "_client", None))
        self._clients.clear()


def _close_quietly(ollama_client: Any) -> None:
    # ollama.Client keeps an httpx.Client in `_client`; close it if the attribute exists.
    http = getattr(ollama_client, "_client", None)
    close = getattr(http, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass