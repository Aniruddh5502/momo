import re
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List

from rich.console import Console
from rich.markdown import Markdown

from momobot.cmd.registry import CommandRegistry, CommandResult
from momobot.bootstrap import sessions_db

console = Console()

theme_char  = "✽"
book_cloth  = "#CC785C"
focus       = "#61AAF2"
cloud_light = "#BFBFBA"
white       = "#FFFFFF"


# ---------------------------------------------------------------------------
# Session metadata (SQLite) — lives alongside the LangGraph checkpoints
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(sessions_db), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_meta (
            thread_id  TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _derive_name(first_message: str) -> str:
    name = (first_message or "").strip().replace("\n", " ")
    if len(name) > 50:
        name = name[:50].rstrip() + "…"
    return name or "(untitled)"


def register_session_name(thread_id: str, first_message: str) -> None:
    now = _now()
    created = False
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM session_meta WHERE thread_id=?", (thread_id,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO session_meta(thread_id, name, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (thread_id, _derive_name(first_message), now, now),
                )
                created = True
            else:
                cur.execute(
                    "UPDATE session_meta SET updated_at=? WHERE thread_id=?",
                    (now, thread_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return

    if created:
        try:
            n = prune_sessions()
            if n:
                console.print(f"[dim]Pruned {n} old session(s) (keeping {MAX_SESSIONS}).[/dim]")
        except Exception:
            pass


def _list_sessions() -> List[Dict[str, str]]:
    if not sessions_db.exists():
        return []

    try:
        conn = _connect()
    except sqlite3.Error:
        return []

    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
            thread_ids = [row[0] for row in cur.fetchall()]
        except sqlite3.OperationalError:
            thread_ids = []

        cur.execute("SELECT thread_id, name, created_at, updated_at FROM session_meta")
        meta = {
            r[0]: {"name": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in cur.fetchall()
        }
    finally:
        conn.close()

    sessions = [
        {"thread_id": tid, "name": None, "created_at": "", "updated_at": "", **meta.get(tid, {})}
        for tid in thread_ids
    ]
    sessions.sort(key=lambda s: s["updated_at"] or s["created_at"] or "", reverse=True)
    return sessions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_SESSIONS = 1000

def _delete_session_data(thread_id: str) -> None:
    conn = _connect()
    try:
        cur = conn.cursor()
        for table in ("checkpoints", "writes"):
            try:
                cur.execute(f"DELETE FROM {table} WHERE thread_id=?", (thread_id,))
            except sqlite3.OperationalError:
                pass
        cur.execute("DELETE FROM session_meta WHERE thread_id=?", (thread_id,))
        conn.commit()
    finally:
        conn.close()


def prune_sessions(max_keep: int = MAX_SESSIONS) -> int:
    sessions = _list_sessions()
    if len(sessions) <= max_keep:
        return 0

    removed = 0
    for s in sessions[max_keep:]:
        try:
            _delete_session_data(s["thread_id"])
            removed += 1
        except Exception as e:
            console.print(f"[dim red]Could not prune {s['thread_id']}: {e}[/dim red]")
    return removed


def _save_current(ui, state: Dict[str, Any]) -> None:
    try:
        ui.agent.app.update_state(
            {"configurable": {"thread_id": ui.current_thread_id}},
            state,
        )
    except Exception as e:
        console.print(f"[dim]Note: could not archive current session: {e}[/dim]")


def _empty_state() -> Dict[str, Any]:
    return {
        "messages": [],
        "summary": "",
        "token_usages": 0,
        "end": "",
        "systemInfo": {},
        "reasoning": False,
        "last_action": "init",
    }


# ---------------------------------------------------------------------------
# Session commands
# ---------------------------------------------------------------------------

def handle_sessions(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
    ui = context.get("ui")
    if ui is None:
        console.print("[bold red]Error: UI context not found.[/bold red]")
        return CommandResult()

    args = args.strip()

    if not args:
        sessions = _list_sessions()
        if not sessions:
            console.print("\n[yellow]No saved sessions found.[/yellow]")
            return CommandResult()

        console.print("\n")
        console.print(Markdown("# RECENT SESSIONS"))
        console.print("\n")
        for i, s in enumerate(sessions, 1):
            current = s["thread_id"] == ui.current_thread_id
            marker = " [bold green]●[/bold green]" if current else ""
            label = s["name"] if s["name"] else s["thread_id"]
            console.print(
                f" [{book_cloth}]{i:>4}[/{book_cloth}]  "
                f"[{cloud_light}]{label}[/{cloud_light}]{marker}"
            )
        console.print("[dim]\nUse /session{i} to resume one of these.\n[/dim]")
        return CommandResult()

    match = re.match(r"(\d+)", args)
    if not match:
        console.print("[bold red]Usage: /session[index] or /session to list.[/bold red]")
        return CommandResult()

    idx = int(match.group(1)) - 1
    sessions = _list_sessions()
    if not (0 <= idx < len(sessions)):
        console.print(f"[bold red]Invalid session index {idx + 1}[/bold red]")
        return CommandResult()

    target = sessions[idx]
    target_tid = target["thread_id"]

    _save_current(ui, state)

    ui.current_thread_id = target_tid
    snapshot = ui.agent.app.get_state({"configurable": {"thread_id": target_tid}})
    new_state = dict(snapshot.values) if snapshot and snapshot.values else {}

    for k, v in _empty_state().items():
        new_state.setdefault(k, v)
    new_state["last_action"] = "resume"

    label = target["name"] or target_tid
    console.print(
        f"\n{theme_char}  [dim]Resuming[/dim] "
        f"[{focus}]{label}[/{focus}] "
        f"[dim]({target_tid}) — {len(new_state['messages'])} messages\n[/dim]"
    )

    return CommandResult(state=new_state, render=True)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_session_commands(registry: CommandRegistry) -> None:

    @registry.register("/help", description="Lists available commands and usages")
    def handle_help(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        cmds = registry.list_commands()
        console.print("\n[bold cyan]Momobot Available Commands:\n[/bold cyan]")
        if not cmds:
            console.print("[yellow]No commands registered.[/yellow]")
            return CommandResult()

        max_len = max(len(c) for c in cmds.keys()) + 4
        for c in sorted(cmds.keys()):
            console.print(
                f"  [bold]{c:<{max_len}}[/bold] [bold]❱[/bold] "
                f"[dim white]{cmds[c]}[/dim white]"
            )
        console.print("[dim]\nUse these commands to manage your session and agent state.\n\n[/dim]")
        return CommandResult()

    @registry.register("/session", description="Resumes a session by index (EX: /session1).")
    def _session_wrapper(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        return handle_sessions(args, state, context)

    @registry.register("/sessions", description="Lists all saved sessions.")
    def _sessions_alias(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        return handle_sessions(args, state, context)

    @registry.register("/clear", description="Archives current session & starts fresh conversation.")
    def handle_clear(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        ui = context.get("ui")
        if ui is None:
            console.print("[bold red]Error: UI context not found.[/bold red]")
            return CommandResult()

        _save_current(ui, state)

        old_tid = ui.current_thread_id
        ui.current_thread_id = str(uuid.uuid4())[:8]

        console.print(f"\n{theme_char}  [dim]Session {old_tid} archived.[/dim]")
        console.print(
            f"\n{theme_char}  [bold {book_cloth}]New session started: "
            f"[{focus}]{ui.current_thread_id}[/{focus}]\n[/bold {book_cloth}]"
        )

        return CommandResult(state=_empty_state())
    
    @registry.register("/delete", description="Deletes a session by index (EX: /delete 3).")
    def handle_delete(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        ui = context.get("ui")
        if ui is None:
            console.print("[bold red]Error: UI context not found.[/bold red]")
            return CommandResult()

        match = re.match(r"(\d+)", args.strip())
        if not match:
            console.print("[bold red]Usage: /delete {index}  (see /sessions for indexes).[/bold red]")
            return CommandResult()

        idx = int(match.group(1)) - 1
        sessions = _list_sessions()
        if not (0 <= idx < len(sessions)):
            console.print(f"[bold red]Invalid session index {idx + 1}[/bold red]")
            return CommandResult()

        target = sessions[idx]
        if target["thread_id"] == ui.current_thread_id:
            console.print(
                "[bold red]Can't delete the active session.[/bold red] "
                "[dim]Run /clear first, then delete it.[/dim]"
            )
            return CommandResult()

        label = target["name"] or target["thread_id"]
        try:
            _delete_session_data(target["thread_id"])
        except Exception as e:
            console.print(f"[bold red]Delete failed:[/bold red] {e}")
            return CommandResult()

        console.print(f"{theme_char} [dim]Deleted session[/dim] [{cloud_light}]{label}[/{cloud_light}]")
        return CommandResult()

    @registry.register("/prune", description=f"Deletes all but the newest {MAX_SESSIONS} sessions.")
    def handle_prune(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        try:
            n = prune_sessions()
        except Exception as e:
            console.print(f"[bold red]Prune failed:[/bold red] {e}")
            return CommandResult()

        if n == 0:
            console.print(f"[dim]Nothing to prune — you have ≤ {MAX_SESSIONS} sessions.[/dim]")
        else:
            console.print(
                f"{theme_char} [dim]Pruned {n} session(s); "
                f"kept the newest {MAX_SESSIONS}.[/dim]"
            )
        return CommandResult()

    # --- Persona Switching Commands ---
    from cmd.persona.persona import switch_persona_handler
    
    @registry.register("/default", description="Switch to default persona")
    def handle_default(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        return switch_persona_handler("default")(args, state, context)

    @registry.register("/plan", description="Switch to planning persona")
    def handle_plan(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        return switch_persona_handler("planner")(args, state, context)

    @registry.register("/review", description="Switch to reviewer persona")
    def handle_review(args: str, state: Dict[str, Any], context: Dict[str, Any]) -> CommandResult:
        return switch_persona_handler("reviewer")(args, state, context)
