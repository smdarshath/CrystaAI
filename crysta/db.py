"""SQLite persistence. All queries are parameterised."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

log = logging.getLogger("crysta.db")

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, created REAL NOT NULL, title TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL,
  content TEXT NOT NULL, agent TEXT, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created);
CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, key TEXT NOT NULL, value TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, body TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
  due REAL, notified INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, notified, due);
CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY, conversation_id TEXT, agent TEXT NOT NULL, status TEXT NOT NULL,
  summary TEXT, duration_ms INTEGER, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS device_pairs (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  can_control INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, last_seen REAL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY, created REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  detail TEXT, outcome TEXT);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created);
"""

SCHEMA_V2 = """
ALTER TABLE tasks ADD COLUMN project TEXT NOT NULL DEFAULT 'General';
ALTER TABLE tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'task';
ALTER TABLE notes ADD COLUMN category TEXT NOT NULL DEFAULT 'general';
ALTER TABLE notes ADD COLUMN project TEXT;
CREATE TABLE IF NOT EXISTS research_history (
  id INTEGER PRIMARY KEY, query TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'web', status TEXT,
  summary TEXT, sources TEXT, created REAL NOT NULL);
"""
MIGRATIONS = [SCHEMA_V1, SCHEMA_V2]  # index+1 == schema version


def now() -> float:
    return time.time()


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self._migrate()

    def _migrate(self):
        with self._lock:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if 0 < version < len(MIGRATIONS):  # keep a copy of existing user data before changing its schema
                import shutil
                self._conn.commit()
                bak = self.path.with_name(f"{self.path.name}.bak-v{version}")
                if not bak.exists():
                    shutil.copy2(self.path, bak)
            for i, script in enumerate(MIGRATIONS, start=1):
                if version < i:
                    self._conn.executescript(script)
                    self._conn.execute(f"PRAGMA user_version={i}")
            self._conn.commit()

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self):
        with self._lock:
            self._conn.close()
