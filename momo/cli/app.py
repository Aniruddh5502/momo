"""REPL entry point:  python -m cli.app [--resume [ID]] [--model TAG] [--project DIR]"""
from __future__ import annotations

import argparse
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from rich.console import Console
from rich.panel import Panel

from momo.cli.animation import ThinkingAnimation
from momo.cli.commands import CommandRegistry, register_builtin_commands
from momo.cli.renderer import Renderer
from momo.core.bootstrap import ensure_momo_dir
from momo.core.harness import Harness
from momo.core.model import ModelFactory
from momo.core.settings import Settings
from momo.store.sessions import SessionStore
from momo.tools.registry import ToolContext, ToolRegistry, register_all
from momo.tools.subagent.manager import SubagentManager

console = Console()

theme_char      =   "✽"
book_cloth      =   "#CC785C"
error           =   "#BF4D43"
focus           =   "#61AAF2"
white           =   "#FFFFFF"
black           =   "#000000"
cloud_light     =   "#BFBFBA"

def build_harness(settings: Settings) -> Harness:
    store = SessionStore(settings.db_path)
    renderer = Renderer()
    animation = ThinkingAnimation()
    model_factory = ModelFactory(settings.ollama_url)
    registry = ToolRegistry()
    tool_ctx = ToolContext(project_root=settings.project_root, session_id="")

    # The manager's emit callback needs the harness, which needs the manager.
    # Resolve the harness lazily through a holder filled in just below.
    holder: dict[str, Harness] = {}
    manager = SubagentManager(
        project_root=settings.project_root,
        registry=registry,
        store=store,
        model_factory=model_factory,
        emit=lambda session, event: holder["harness"]._emit(session, event),
        on_progress=animation.add_tokens,
        register_color=renderer.register_agent_color,
    )
    tool_ctx.subagent_manager = manager
    register_all(registry, tool_ctx)

    commands = CommandRegistry()
    register_builtin_commands(commands)
    harness = Harness(
        settings, registry, store, renderer, commands,
        model_factory=model_factory,
        tool_context=tool_ctx,
        animation=animation,
        subagent_manager=manager,
    )
    holder["harness"] = harness
    return harness


def _make_session() -> PromptSession:
        """Configures the prompt toolkit session with production keybindings."""
        bindings = KeyBindings()
        @bindings.add("escape", "enter")
        def _submit(event):
            event.current_buffer.validate_and_handle()
        @bindings.add("enter")
        def _newline(event):
            event.current_buffer.insert_text("\n")
        return PromptSession(key_bindings=bindings, multiline=True)

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="momo")
    parser.add_argument("--resume", nargs="?", const="latest", default=None, metavar="ID",
                        help="resume the latest session, or the one matching ID")
    parser.add_argument("--model", default=None, help="Ollama model tag")
    parser.add_argument("--project", default=None, help="project root (default: current directory)")
    args = parser.parse_args(argv)

    settings = Settings()
    if args.project:
        settings.project_root = Path(args.project).resolve()
    if args.model:
        settings.model = args.model

    # creating .momo/ in the new workspace
    ensure_momo_dir(settings.project_root)

    harness = build_harness(settings)
    renderer = harness.renderer

    if args.resume is not None:
        session = harness.resume(args.resume)
        harness.replay(session)
    else:
        session = harness.new_session()
    
    prompt_session = _make_session()
    
    print("\n\n\n\n\n\n\n\n")
    console.print(f"[{book_cloth}]{theme_char} Momo Bot[/]")
    renderer.info(f"momo · {session.spec.model} · session {session.id[:8]} · /help for commands")
    print("\n\n")
    while True:
        try:
            console.rule()
            text = prompt_session.prompt(ANSI("\x1b[1;36m ⟩  \x1b[0m"))
            console.rule()
        except (EOFError, KeyboardInterrupt):
            console.rule()
            renderer.console.print()
            break
        try:
            session = harness.handle(session, text)
        except SystemExit:
            break


if __name__ == "__main__":
    main()