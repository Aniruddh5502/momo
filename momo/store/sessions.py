"""Session + SessionStore: persistence for LLM context (messages) and the render log (events)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from momo.core.events import Event, EventType
from momo.core.spec import AgentSpec
from momo.store.db import connect


@dataclass
class Session:
    id: str
    parent_id: str | None
    agent_name: str
    project_root: Path
    spec: AgentSpec
    title: str | None


class SessionStore:
    def __init__(self, db_path: Path | str) -> None:
        self.conn = connect(db_path)

    # ------------------------------------------------------------------ sessions
    def create(self, spec: AgentSpec, project_root: Path, parent_id: str | None = None,
               session_id: str | None = None) -> Session:
        session_id = session_id or uuid.uuid4().hex
        now = time.time()
        with self.conn:
            self.conn.execute(
                "INSERT INTO sessions (id, parent_id, agent_name, project_root, spec_json, title, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
                (session_id, parent_id, spec.name, str(project_root), spec.to_json(), now, now),
            )
        return Session(session_id, parent_id, spec.name, Path(project_root), spec, None)

    def get(self, session_id: str) -> Session:
        """Look up by full id or unique prefix."""
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ? OR id LIKE ? LIMIT 2", (session_id, session_id + "%")
        ).fetchall()
        exact = [r for r in rows if r["id"] == session_id]
        if exact:
            return self._row_to_session(exact[0])
        if not rows:
            raise KeyError(f"No session matching '{session_id}'")
        if len(rows) > 1:
            raise ValueError(f"Session id prefix '{session_id}' is ambiguous")
        return self._row_to_session(rows[0])

    def exists(self, session_id: str) -> bool:
        """Exact match only. Use this instead of get() when deciding whether to create."""
        return self.conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone() is not None

    def list(self, project_root: Path | None = None, limit: int = 50) -> list[Session]:
        sql, params = "SELECT * FROM sessions WHERE parent_id IS NULL", []
        if project_root is not None:
            sql += " AND project_root = ?"
            params.append(str(project_root))
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [self._row_to_session(r) for r in self.conn.execute(sql, params)]

    def latest(self, project_root: Path) -> Session | None:
        sessions = self.list(project_root, limit=1)
        return sessions[0] if sessions else None

    def set_title(self, session_id: str, title: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))

    def update_spec(self, session_id: str, spec: AgentSpec) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET spec_json = ?, updated_at = ? WHERE id = ?",
                (spec.to_json(), time.time(), session_id),
            )

    # ------------------------------------------------------------------ LLM context
    def load_messages(self, session_id: str) -> list[BaseMessage]:
        rows = self.conn.execute(
            "SELECT msg_json FROM messages WHERE session_id = ? AND compacted = 0 ORDER BY seq",
            (session_id,),
        ).fetchall()
        return messages_from_dict([json.loads(r["msg_json"]) for r in rows])

    def replace_messages(self, session_id: str, messages: list[BaseMessage]) -> None:
        """Make `messages` the session's active context.

        Pure append inserts only the tail. Anything else (compaction rewrote history)
        marks the old rows compacted and re-inserts the whole list.
        """
        for m in messages:
            if not m.id:
                m.id = uuid.uuid4().hex
        new_ids = [m.id for m in messages]
        with self.conn:
            rows = self.conn.execute(
                "SELECT msg_json FROM messages WHERE session_id = ? AND compacted = 0 ORDER BY seq",
                (session_id,),
            ).fetchall()
            old_ids = [json.loads(r["msg_json"])["data"].get("id") for r in rows]
            if new_ids[: len(old_ids)] == old_ids:
                tail = messages[len(old_ids):]
            else:
                self.conn.execute(
                    "UPDATE messages SET compacted = 1 WHERE session_id = ? AND compacted = 0",
                    (session_id,),
                )
                tail = messages
            next_seq = self.conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            for offset, m in enumerate(tail):
                self.conn.execute(
                    "INSERT INTO messages (session_id, seq, msg_json, compacted) VALUES (?, ?, ?, 0)",
                    (session_id, next_seq + offset, json.dumps(messages_to_dict([m])[0], default=str)),
                )
            self.conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), session_id))

    # ------------------------------------------------------------------ render log
    def append_event(self, event: Event) -> Event:
        """Append to the render log; assigns `seq` (and `ts` if unset)."""
        if not event.ts:
            event.ts = time.time()
        payload = dict(event.payload, _agent=event.agent) if event.agent else event.payload
        with self.conn:
            event.seq = self.conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?", (event.session_id,)
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO events (session_id, seq, type, payload_json, ts) VALUES (?, ?, ?, ?, ?)",
                (event.session_id, event.seq, event.type.value, json.dumps(payload, default=str), event.ts),
            )
            self.conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (event.ts, event.session_id))
        return event

    def load_events(self, session_id: str, after_seq: int = 0) -> Iterator[Event]:
        cursor = self.conn.execute(
            "SELECT seq, type, payload_json, ts FROM events WHERE session_id = ? AND seq > ? ORDER BY seq",
            (session_id, after_seq),
        )
        for row in cursor:
            payload = json.loads(row["payload_json"])
            agent = payload.pop("_agent", "")
            yield Event(
                type=EventType(row["type"]),
                payload=payload,
                session_id=session_id,
                seq=row["seq"],
                ts=row["ts"],
                agent=agent,
            )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _row_to_session(row) -> Session:
        return Session(
            id=row["id"],
            parent_id=row["parent_id"],
            agent_name=row["agent_name"],
            project_root=Path(row["project_root"]),
            spec=AgentSpec.from_json(row["spec_json"]),
            title=row["title"],
        )