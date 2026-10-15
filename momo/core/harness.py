"""Harness: owns I/O. Resolves config, builds the agent on every prompt, persists and renders events."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from momo.cli.commands import CommandContext, CommandRegistry
from momo.cli.renderer import Renderer
from momo.core.agent import Agent, repair_dangling_tool_calls
from momo.core.compactor import Compactor, TokenTracker
from momo.core.events import Event, EventType
from momo.core.model import ModelFactory
from momo.core.prompt import PromptBuilder
from momo.core.settings import Settings
from momo.core.spec import AgentSpec
from momo.store.sessions import Session, SessionStore
from momo.tools.registry import ToolContext, ToolRegistry

if TYPE_CHECKING:
    from momo.cli.animation import ThinkingAnimation
    from momo.tools.subagent.manager import SubagentManager


class Harness:
    def __init__(
        self,
        settings: Settings,
        tools: ToolRegistry,
        store: SessionStore,
        renderer: Renderer,
        commands: CommandRegistry,
        *,
        model_factory: ModelFactory | None = None,
        prompt_builder: PromptBuilder | None = None,
        tool_context: ToolContext | None = None,
        animation: "ThinkingAnimation | None" = None,
        subagent_manager: "SubagentManager | None" = None,
    ) -> None:
        self.settings = settings
        self.tools = tools
        self.store = store
        self.renderer = renderer
        self.commands = commands
        self.model_factory = model_factory or ModelFactory(settings.ollama_url)
        self.prompt_builder = prompt_builder or PromptBuilder(settings.prompts_dir)
        self.tool_context = tool_context
        self.animation = animation
        self.subagent_manager = subagent_manager
        self._turn_active = False               # spinner only runs inside a turn
        self.session: Session | None = None     # the active session

    # ------------------------------------------------------------------ sessions
    def new_session(self, agent_name: str = "main") -> Session:
        session = self.store.create(self._default_spec(agent_name), self.settings.project_root)
        self._activate(session)
        return session

    def resume(self, session_id: str | None = None) -> Session:
        """Resume by id/prefix, or the latest session for this project (new one if none exist)."""
        if session_id in (None, "", "latest"):
            session = self.store.latest(self.settings.project_root)
            if session is None:
                return self.new_session()
        else:
            session = self.store.get(session_id)
        self._activate(session)
        return session

    def replay(self, session: Session) -> None:
        self.renderer.render_replay(self.store.load_events(session.id))

    # ------------------------------------------------------------------ main entry point
    def handle(self, session: Session, text: str) -> Session:
        """Entry point for every line of user input. Returns the active session
        (which a command such as /clear or /resume may have switched)."""
        text = text.strip()
        if not text:
            return session

        ctx = CommandContext(harness=self, session=session, renderer=self.renderer, args="")
        result = self.commands.try_dispatch(text, ctx)
        if result is not None:
            if result.new_session is not None:
                session = result.new_session
                self._activate(session)
            if result.inject_prompt is None:
                return session
            text = result.inject_prompt

        self._run_turn(session, text)
        return session

    def compact_session(self, session: Session) -> None:
        """Force compaction now (/compact), regardless of the threshold."""
        agent = self._build_agent(session.spec, session.project_root)
        messages = self.store.load_messages(session.id)
        result = agent.compactor.compact(messages)
        if not result.compacted:
            self.renderer.info("Nothing to compact yet.")
            return
        self.store.replace_messages(session.id, result.messages)
        self._emit(session, Event(EventType.COMPACTION, {
            "summary": result.summary,
            "tokens_before": result.tokens_before,
            "tokens_after": result.tokens_after,
            "dropped": len(messages) - len(result.messages) + 1,
        }))

    # ------------------------------------------------------------------ internals
    def _run_turn(self, session: Session, text: str) -> None:
        if self.subagent_manager:
            self.subagent_manager.set_active_session_id(session.id)
        agent = self._build_agent(session.spec, session.project_root)
        messages = self.store.load_messages(session.id)
        if session.title is None:
            session.title = text[:60]
            self.store.set_title(session.id, session.title)
        self._turn_active = True
        if self.animation:
            self.animation.reset()
        try:
            for event in agent.run(messages, text):
                self._emit(session, event)
        except KeyboardInterrupt:
            self._emit(session, Event(EventType.ERROR, {"message": "Interrupted.", "recoverable": True}))
            self._emit(session, Event(EventType.TURN_END, {}))
        except Exception as exc:    # e.g. Ollama unreachable: keep the session usable
            self._emit(session, Event(EventType.ERROR, {"message": f"{type(exc).__name__}: {exc}", "recoverable": False}))
            self._emit(session, Event(EventType.TURN_END, {}))
        finally:
            self._turn_active = False
            if self.animation:
                self.animation.stop()
            if agent.messages:      # never overwrite history with an empty list
                self.store.replace_messages(session.id, repair_dangling_tool_calls(agent.messages))

    def _emit(self, session: Session, event: Event) -> None:
        anim = self.animation
        if anim:
            anim.stop()                  # clear the spinner line before anything is printed
        event.session_id = session.id
        self.store.append_event(event)
        self.renderer.render(event)
        if anim and self._turn_active and event.type != EventType.TURN_END:
            anim.start()                 # the agent keeps working until the next event

    def _build_agent(self, spec: AgentSpec, project_root: Path | None = None) -> Agent:
        """Rebuilt from config on every prompt: prompts are re-read, tools resolved by the spec."""
        root = project_root or self.settings.project_root
        tools = self.tools.resolve(spec.tools)
        model = self.model_factory.build(spec, tools)
        summarizer = self.model_factory.build(spec, [])
        compactor = Compactor(summarizer, TokenTracker(max_context=spec.max_context_tokens), spec.keep_recent_messages)
        prompt = self.prompt_builder.build(
            spec, tools,
            dynamic={"environment": PromptBuilder.environment(root)},
            project_root=root,
        )
        on_progress = self.animation.add_tokens if self.animation else None
        agent = Agent(spec, prompt, tools, model, compactor, on_progress=on_progress)
        agent.compile()
        return agent

    def _default_spec(self, agent_name: str = "main") -> AgentSpec:
        s = self.settings
        return AgentSpec(
            name=agent_name,
            model=s.model,
            num_ctx=s.num_ctx,
            prompt_sections=list(s.prompt_sections),
            tools=self.tools.names(),
            max_context_tokens=s.max_context_tokens,
            keep_recent_messages=s.keep_recent_messages,
            max_iterations=s.max_iterations,
            temperature=s.temperature,
        )

    def _activate(self, session: Session) -> None:
        self.session = session
        if self.tool_context is not None:
            self.tool_context.session_id = session.id
            self.tool_context.project_root = session.project_root