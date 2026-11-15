"""Settings: process-wide defaults. Everything agent-specific lives in AgentSpec."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    project_root: Path = field(default_factory=Path.cwd)
    provider:str = "ollama"
    url:str = ""
    ollama_url: str = "https://openrouter.ai/api/v1"
    model: str = "ornith-1.5:9b"
    num_ctx: int = 30000                 # must be >= max_context_tokens + headroom
    max_context_tokens: int = 30000      # compaction threshold
    keep_recent_messages: int = 6
    max_iterations: int = 250
    temperature: float = 0.5
    prompt_sections: tuple[str, ...] = ("soul", "user", "tool")
    # Phase 1: one DB for all projects (sessions are keyed by project_root).
    # Phase 2 moves this to <project>/.momo/sessions.db.
    db_path: Path = field(default_factory=lambda: Path.home() / ".momo" / "sessions.db")
    prompts_dir: Path = _PACKAGE_ROOT / "prompts"