"""Subagents: persistent child sessions that run through the same Agent and emit path."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace, asdict
from pathlib import Path
from typing import Any, Callable, TypedDict

import frontmatter
from rich.errors import StyleSyntaxError
from rich.style import Style

from momo.core.agent import Agent, repair_dangling_tool_calls
from momo.core.compactor import Compactor, TokenTracker
from momo.core.events import Event, EventType
from momo.core.model import ModelFactory
from momo.core.settings import Settings
from momo.core.spec import AgentSpec
from momo.store.sessions import Session, SessionStore
from momo.tools.registry import ToolRegistry

@dataclass
class SubagentState:
    version: int
    offset: int
    messages: list[Any] # Using Any to match SessionStore message types

SUBAGENT_TOOL = "call_subagent"                 # subagents never get this tool (no recursion)
SUBAGENT_EXCLUDED_TAGS = {"orchestration"}      # any tool with these tags is never given to a subagent


# ---------------------------------------------------------------------- reading agent files
def load_agent_file(path: Path) -> dict[str, Any]:
    """Read one agent .md file: every frontmatter field, plus the body as `content`."""
    with open(path, "r", encoding="utf-8") as file:
        post = frontmatter.load(file)
    return {
        "name": post.get("name"),
        "description": post.get("description"),
        "model": post.get("model"),
        # accept the old misspelling too, so an existing file doesn't silently lose its tools
        "tool_categories": post.get("tool_categories", post.get("tool_catagories")),
        "color": post.get("color"),
        "sessions": post.get("sessions"),
        "type": post.get("type"),
        "metadata": dict(post.metadata),     # every key, for optional numeric settings
        "path": path,
        "content": post.content,
    }


def get_agents(agents_path: Path) -> list[dict[str, Any]]:
    """All agent files under `agents_path` as dicts. A file that fails to parse is returned
    with an `error` key instead of raising, so one broken file can't hide the others."""
    agents: list[dict[str, Any]] = []
    for path in sorted(Path(agents_path).rglob("*.md")):
        try:
            agents.append(load_agent_file(path))
        except Exception as exc:
            agents.append({"name": path.stem, "path": path, "error": f"{type(exc).__name__}: {exc}"})
    return agents


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _valid_color(value: Any) -> str | None:
    """A Rich style string, or None if missing or unparseable (the renderer then uses its palette)."""
    if not value:
        return None
    text = str(value).strip()
    try:
        Style.parse(text)
    except StyleSyntaxError:
        return None
    return text

@dataclass
class SubagentConfig:
    spec: AgentSpec
    system_prompt: str
    tool_categories: list[str]
    description: str = ""
    color: str | None = None
    sessions: list[str] = field(default_factory=list)
    type: str | None = None
    path: Path | None = None


class SubagentParser:
    @staticmethod
    def parse(path: Path, settings: Settings | None = None) -> SubagentConfig:
        """Build a SubagentConfig from an agent file. Anything the file omits falls back to Settings."""
        s = settings or Settings()
        data = load_agent_file(path)
        meta = data["metadata"]

        def number(key: str, default: Any, cast: Callable[[Any], Any]) -> Any:
            return cast(meta[key]) if meta.get(key) is not None else default

        color = _valid_color(data["color"])
        spec = AgentSpec(
            name=str(data["name"] or path.stem),
            model=str(data["model"] or s.model),
            num_ctx=number("num_ctx", s.num_ctx, int),
            prompt_sections=[],                  # the body is the whole prompt
            tools=[],                            # filled in by the manager
            max_context_tokens=number("max_context_tokens", s.max_context_tokens, int),
            keep_recent_messages=number("keep_recent_messages", s.keep_recent_messages, int),
            max_iterations=number("max_iterations", s.max_iterations, int),
            temperature=number("temperature", s.temperature, float),
            extra={"color": color} if color else {},
        )
        return SubagentConfig(
            spec=spec,
            system_prompt=data["content"].strip(),
            tool_categories=_as_list(data["tool_categories"]),
            description=str(data["description"] or ""),
            color=color,
            sessions=_as_list(data["sessions"]),
            type=str(data["type"]) if data["type"] else None,
            path=path,
        )


# ---------------------------------------------------------------------- manager
class SubagentManager:
    def __init__(
        self,
        project_root: Path,
        registry: ToolRegistry,
        store: SessionStore,
        model_factory: ModelFactory,
        emit: Callable[[Session, Event], None],
        on_progress: Callable[[int], None] | None = None,
        register_color: Callable[[str, str], None] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.project_root = project_root
        self.registry = registry
        self.store = store
        self.model_factory = model_factory
        self.emit = emit                  # harness._emit: stops/starts spinner, persists, renders
        self.on_progress = on_progress    # animation.add_tokens
        self.register_color = register_color
        self.settings = settings or Settings(project_root=project_root)
        self._active_session_id: str | None = None

    def set_active_session_id(self, session_id: str) -> None:
        self._active_session_id = session_id

    def get_active_session_id(self) -> str | None:
        return self._active_session_id

    @property
    def agents_dir(self) -> Path:
        return self.project_root / ".momo" / "agents"

    def agent_path(self, name: str) -> Path | None:
        """<name>.md directly, otherwise any agent file whose frontmatter `name` matches."""
        direct = self.agents_dir / f"{name}.md"
        if direct.is_file():
            return direct
        for entry in get_agents(self.agents_dir):
            if entry.get("name") == name and not entry.get("error"):
                return entry["path"]
        return None

    def run_subagent(self, name: str, prompt: str, main_session_id: str, new_chat: bool = False) -> str:
        path = self.agent_path(name)
        if path is None:
            available = ", ".join(a["name"] for a in get_agents(self.agents_dir) if not a.get("error")) or "(none)"
            return f"Error: subagent '{name}' not found in {self.agents_dir}. Available: {available}"
        try:
            config = SubagentParser.parse(path, self.settings)
        except Exception as exc:          # bad YAML, non-numeric num_ctx, unreadable file...
            return f"Error: could not read {path.name}: {type(exc).__name__}: {exc}"
        if config.color and self.register_color:
            self.register_color(config.spec.name, config.color)

        tool_names: list[str] = []
        for cat in config.tool_categories:
            for n in self.registry.names(tag=cat):
                if n == SUBAGENT_TOOL or n in tool_names:
                    continue
                if SUBAGENT_EXCLUDED_TAGS & self.registry.tags(n):
                    continue
                tool_names.append(n)
        tools = self.registry.resolve(tool_names)
        spec = replace(config.spec, tools=tool_names)

        sub_id = f"sub_{main_session_id}_{name}"
        
        # 1. Load and Migrate State
        raw_state = self.store.load_messages(sub_id) if self.store.exists(sub_id) else None
        if raw_state is None:
            state = SubagentState(version=1, offset=0, messages=[])
        elif isinstance(raw_state, list):
            state = SubagentState(version=1, offset=0, messages=raw_state)
        elif isinstance(raw_state, dict):
            state = SubagentState(**raw_state)
        else:
            state = SubagentState(version=1, offset=0, messages=[])

        # 2. Determine window and update state metadata
        if new_chat:
            state.offset = len(state.messages)
            state.version += 1
            messages_to_use = [] 
        else:
            messages_to_use = state.messages[state.offset:]

        # 3. Agent Setup
        if not self.store.exists(sub_id):
             child = self.store.create(spec, self.project_root, parent_id=main_session_id, session_id=sub_id)
        else:
             child = self.store.get(sub_id)

        # Guard: Ensure child is a Session object for self.emit
        if not hasattr(child, 'id'):
            # Fallback if store.get returned something other than a Session object
            from momo.store.sessions import Session
            child = Session(id=str(child), parent_id=main_session_id, agent_name=name, project_root=self.project_root, spec=spec, title=None)

        model = self.model_factory.build(spec, tools)
        summarizer = self.model_factory.build(spec, [])
        compactor = Compactor(summarizer, TokenTracker(spec.max_context_tokens), spec.keep_recent_messages)
        agent = Agent(spec, config.system_prompt, tools, model, compactor, on_progress=self.on_progress)
        agent.compile()

        final_text = ""
        error: str | None = None
        try:
            for event in agent.run(messages_to_use, prompt):
                # The crash is likely here in self.emit(child, event)
                # Let's ensure the Event itself has the session_id
                if not event.session_id:
                    event.session_id = child.id if hasattr(child, 'id') else str(child)
                
                # Final safety check for the session object
                session_obj = child if hasattr(child, 'id') else Session(
                    id=str(child), 
                    parent_id=main_session_id, 
                    agent_name=name, 
                    project_root=self.project_root, 
                    spec=spec, 
                    title=None
                )
                
                self.emit(session_obj, event)
                
                if event.type == EventType.ASSISTANT_TEXT:
                    final_text = event.payload["text"]
                elif event.type == EventType.ERROR and not event.payload.get("recoverable", False):
                    error = event.payload.get("message", "unknown error")
        except Exception as exc:          # report instead of letting the parent's tool node fail
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if agent.messages:
                # CRITICAL FIX: Only append NEW messages to avoid exponential history growth
                input_len = len(messages_to_use)
                new_messages = agent.messages[input_len:]
                updated_history = state.messages + new_messages
                
                # replace_messages takes a plain list of messages (not a dict)
                self.store.replace_messages(sub_id, repair_dangling_tool_calls(updated_history))

        if error:
            return f"Subagent error: {error}"
        return final_text or "Subagent finished without a text response."