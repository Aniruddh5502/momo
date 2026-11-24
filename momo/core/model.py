"""ModelFactory: builds OpenRouter chat models for specs.

One ChatOpenAI client is created per distinct model configuration and reused for every
turn, subagent call and summarizer. `bind_tools` is cheap, so tools are bound per call.
"""
from __future__ import annotations

import atexit
import json
import os
from typing import TYPE_CHECKING, Any, Optional

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from momo.core.spec import AgentSpec

load_dotenv()

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ModelFactory:
    def __init__(self,base_url: str = OPENROUTER_BASE_URL, api_key: str | None = None) -> None:
        self.provider = os.environ.get("PROVIDER","ollama")
        
        if self.provider    ==  "ollama":
            self.base_url   =   "http://localhost:11434"
            self.model      =   os.environ.get("MODEL_NAME","ornith-1.5:9b")
            self._clients: dict[tuple, ChatOllama] = {}
            atexit.register(self.close)
        
        if self.provider    ==  "openrouter":
            self.base_url   =   "https://openrouter.ai/api/v1"
            self.model      =   os.environ.get("MODEL_NAME", "nvidia/nemotron-3.5-lightning:free")
            self.api_key  = api_key or os.environ.get("OPENROUTER_API_KEY","")
            if not self.api_key:
                raise RuntimeError("OPENROUTER_API_KEY is not set in .env file.\nFormat should be OPENROUTER_API_KEY='api_key_string'")
            self._clients:dict[tuple, ChatOpenAI] = {}
            atexit.register(self.close)
        
        if self.provider    ==  "unsloth":
            self.base_url   =   "http://localhost:8888/v1"
            self.model      =   os.environ.get("MODEL_NAME","")
            self.api_key    =   api_key or os.environ.get("UNSLOTH_API_KEY","")
            if not self.api_key:
                raise RuntimeError("UNSLOTH_API_KEY is not set in the .env file")
            self._clients:dict[tuple, ChatOpenAI] = {}
            atexit.register(self.close)
    
    def build(self, spec: AgentSpec, tools: list[BaseTool]) -> "Runnable":
        llm = self._client(spec)
        return llm.bind_tools(tools) if tools else llm

    def _client(self, spec: AgentSpec) -> Any[ChatOpenAI, ChatOllama]:
        
        if self.provider == "openrouter":
            key = spec.name
            if key not in self._clients:
                self._clients[key] = ChatOpenAI(
                    model=spec.model,          # OpenRouter slug, e.g. "qwen/qwen-2.5-72b-instruct"
                    base_url=self.base_url,
                    api_key=self.api_key,
                    temperature=spec.temperature,
                    stream_usage=False,         # report token counts on the final streamed chunk
                    max_retries=2,
                )
            return self._clients[key]
        
        if self.provider == "ollama":
            key = spec.name
            self._clients[key]=ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=spec.temperature,
                reasoning=False,
                disable_streaming=False,
                keep_alive=-1,
                num_ctx=spec.num_ctx,
                num_thread=6,
                num_gpu=0,
                repeat_last_n=1000,
                repeat_penalty=1.05,
            )
            return self._clients[key]
        
        if self.provider=="unsloth":
            key=spec.name
            self._clients[key]=ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=1,
                disable_streaming=False
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