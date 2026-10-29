"""PromptBuilder: assembles the system prompt.

Ordering matters for Ollama's prompt-prefix reuse: static content first, dynamic
content last. Static sections come from `spec.prompt_sections` in order; dynamic
sections come from the `dynamic` dict in insertion order, so callers should put
the most volatile items (date, cwd) at the end.

Suggested dynamic keys, in order:
    project_instructions, skills_index, subagents_index, memory, environment
"""
from __future__ import annotations

import datetime as _dt
import platform, shutil, subprocess
from pathlib import Path
from langchain_core.tools import BaseTool
from momo.core.spec import AgentSpec
from momo.core.discovery import agent_and_skill

TOOLS_SECTION = "@tools"   # special section name: renders tool names + descriptions


class PromptBuilder:
    def __init__(self, sections_dir: Path) -> None:
        self.sections_dir = Path(sections_dir)

    def build(
        self,
        spec: AgentSpec,
        tools: list[BaseTool],
        *,
        dynamic: dict[str, str] | None = None,
        project_root: Path | None = None,
    ) -> str:
        parts: list[str] = []
        for name in spec.prompt_sections:
            if name == TOOLS_SECTION:
                parts.append(self._render_tools(tools))
            else:
                parts.append(self._read_section(name))
        for key, content in (dynamic or {}).items():
            content = (content or "").strip()
            if content:
                parts.append(f"<{key}>\n{content}\n</{key}>")
        
        system_prompt_1 = "\n\n".join(p for p in parts if p)
        
        # .momo/ lives in the project root the harness is working in (--project), so the
        # caller passes it; fall back to the current directory only if nothing was passed.
        root_dir = project_root if project_root is not None else Path.cwd()
        system_prompt_2 = agent_and_skill(root_dir / ".momo")

        return f"{system_prompt_1}\n{system_prompt_2}"

    # ------------------------------------------------------------------ helpers
    def _read_section(self, name: str) -> str:
        path = self.sections_dir / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt section '{name}' not found at {path}")
        return path.read_text(encoding="utf-8").strip()


    @staticmethod
    def _render_tools(tools: list[BaseTool]) -> str:
        lines = ["# Tools"]
        for t in tools:
            lines.append(f"- {t.name}: {t.description.strip().splitlines()[0] if t.description else ''}")
        return "\n".join(lines)



    # @staticmethod is a decorator that tells Python: "this method doesn't 
    # take self (or cls) — it's just a plain function that happens to live 
    # inside the class."
    # gets the environment data from the CWD
    @staticmethod
    def git_status(root: Path) -> str:
        git = shutil.which("git")
        if not git:
            return "git: not installed"

        def run(*args: str) -> str:
            return subprocess.run(
                [git, *args],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2,
                errors="replace",
            ).stdout.strip()

        try:
            top = run("rev-parse", "--show-toplevel")
            if not top:
                return "git: not a repository"
            branch = run("rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
            changes = run("status", "--porcelain")
            dirty = "dirty" if changes else "clean"
            files = len(changes.splitlines())
            suffix = f", {files} changed file(s)" if files else ""
            return f"git: {top} @ {branch} ({dirty}{suffix})"
        except (OSError, subprocess.SubprocessError) as e:
            return f"git: unavailable ({e.__class__.__name__})"

    @staticmethod
    def environment(project_root: Path) -> str:
        """Volatile facts: keep this last in the dynamic dict."""
        root = Path(project_root).resolve()
        return (
            f"date: {_dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"cwd: {root}\n"
            f"os: {platform.platform()}\n"
            f"machine: {platform.machine()}\n"
            f"python: {platform.python_version()}\n"
            f"{PromptBuilder.git_status(root)}"
        )
