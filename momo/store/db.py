"""SQLite connection and migrations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS sessions (
  id           TEXT PRIMARY KEY,
  parent_id    TEXT REFERENCES sessions(id),   -- NULL for main sessions
  agent_name   TEXT NOT NULL,
  project_root TEXT NOT NULL,
  spec_json    TEXT NOT NULL,                  -- snapshot of AgentSpec at creation
  title        TEXT,
  created_at   REAL NOT NULL,
  updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL REFERENCES sessions(id),
  seq         INTEGER NOT NULL,
  msg_json    TEXT NOT NULL,                   -- serialized LangChain message
  compacted   INTEGER NOT NULL DEFAULT 0,
  UNIQUE(session_id, seq)
);

CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id   TEXT NOT NULL REFERENCES sessions(id),
  seq          INTEGER NOT NULL,
  type         TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ts           REAL NOT NULL,
  UNIQUE(session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open the database (WAL mode, foreign keys on) and apply migrations.

    One connection per thread: create a new one for any subagent thread.
    """
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(SCHEMA_V1)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()
