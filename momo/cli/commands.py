"""Slash commands: abstractions + the builtin Python commands (no LLM call).

Phase 3 adds PromptCommand / AgentCommand loaded from markdown files; they plug into
the same registry and return CommandResult(inject_prompt=...).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from momo.store.sessions import Session

if TYPE_CHECKING:
    from momo.cli.renderer import Renderer
    from momo.core.harness import Harness


@dataclass
class CommandContext:
    harness: "Harness"
    session: Session
    renderer: "Renderer"
    args: str


@dataclass
class CommandResult:
    handled: bool = True
    inject_prompt: str | None = None     # PromptCommand: text to send to the agent
    new_session: Session | None = None   # /clear, /resume switch the active session


class Command(Protocol):
    name: str
    description: str

    def run(self, ctx: CommandContext) -> CommandResult: ...


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        self._commands[cmd.name] = cmd

    def all(self) -> list[Command]:
        return sorted(self._commands.values(), key=lambda c: c.name)

    def try_dispatch(self, text: str, ctx: CommandContext) -> CommandResult | None:
        """None means 'not a command'; otherwise the command's result."""
        if not text.startswith("/"):
            return None
        name, _, args = text[1:].partition(" ")
        cmd = self._commands.get(name)
        if cmd is None:
            ctx.renderer.info(f"Unknown command: /{name}. Try /help.", style="red")
            return CommandResult(handled=True)
        return cmd.run(replace(ctx, args=args.strip()))


# ---------------------------------------------------------------------- builtin commands
class _Base:
    name = ""
    description = ""


class ClearCommand(_Base):
    name, description = "clear", "Start a fresh session"

    def run(self, ctx: CommandContext) -> CommandResult:
        session = ctx.harness.new_session()
        ctx.renderer.info("Started a new session.")
        return CommandResult(new_session=session)


class ResumeCommand(_Base):
    name, description = "resume", "Resume a session: /resume [id-prefix] (default: latest)"

    def run(self, ctx: CommandContext) -> CommandResult:
        try:
            session = ctx.harness.resume(ctx.args or None)
        except (KeyError, ValueError) as exc:
            ctx.renderer.info(str(exc), style="red")
            return CommandResult()
        ctx.harness.replay(session)
        return CommandResult(new_session=session)


class SessionsCommand(_Base):
    name, description = "sessions", "List recent sessions for this project"

    def run(self, ctx: CommandContext) -> CommandResult:
        sessions = ctx.harness.store.list(ctx.session.project_root, limit=10)
        if not sessions:
            ctx.renderer.info("No sessions yet.")
        for s in sessions:
            marker = "*" if s.id == ctx.session.id else " "
            ctx.renderer.info(f"{marker} {s.id[:8]}  {s.title or '(untitled)'}")
        return CommandResult()


class CompactCommand(_Base):
    name, description = "compact", "Summarize older messages now"

    def run(self, ctx: CommandContext) -> CommandResult:
        ctx.harness.compact_session(ctx.session)
        return CommandResult()


class ModelCommand(_Base):
    name, description = "model", "Show or change the model: /model [tag]"

    def run(self, ctx: CommandContext) -> CommandResult:
        spec = ctx.session.spec
        if not ctx.args:
            ctx.renderer.info(f"Model: {spec.model}")
            return CommandResult()
        new_spec = replace(spec, model=ctx.args)
        ctx.harness.store.update_spec(ctx.session.id, new_spec)
        ctx.session.spec = new_spec
        ctx.renderer.info(f"Model set to {ctx.args} for this session.")
        return CommandResult()


class HelpCommand(_Base):
    name, description = "help", "List commands"

    def run(self, ctx: CommandContext) -> CommandResult:
        for cmd in ctx.harness.commands.all():
            ctx.renderer.info(f"/{cmd.name:<10} {cmd.description}")
        return CommandResult()


class ExitCommand(_Base):
    name, description = "exit", "Quit"

    def run(self, ctx: CommandContext) -> CommandResult:
        raise SystemExit(0)


def register_builtin_commands(registry: CommandRegistry) -> None:
    for cmd in (ClearCommand(), ResumeCommand(), SessionsCommand(), CompactCommand(),
                ModelCommand(), HelpCommand(), ExitCommand()):
        registry.register(cmd)
