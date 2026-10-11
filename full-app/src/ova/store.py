"""One SQLite file for everything the runtime must remember.

Calls and their transcripts, spans for the trace, operations and promises, messages sent on
other channels, uploaded files, and the packs' own records (policies, claims, bookings) as JSON.
Standard library only. One connection with a lock: every statement is short, and the call path
never waits on anything slower than a local write. Postgres can replace this module (M3).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY, tenant TEXT, channel TEXT, caller TEXT,
  started_at REAL, ended_at REAL, outcome TEXT, summary TEXT, state_json TEXT);
CREATE TABLE IF NOT EXISTS turns (
  call_id TEXT, n INTEGER, t REAL, who TEXT, text TEXT, speech TEXT, meta_json TEXT);
CREATE INDEX IF NOT EXISTS turns_call ON turns(call_id, n);
CREATE TABLE IF NOT EXISTS spans (
  call_id TEXT, turn INTEGER, layer TEXT, name TEXT, start_ms REAL, end_ms REAL,
  meta_json TEXT);
CREATE INDEX IF NOT EXISTS spans_call ON spans(call_id, turn);
CREATE TABLE IF NOT EXISTS operations (
  id TEXT PRIMARY KEY, call_id TEXT, tool TEXT, terms_json TEXT, state TEXT,
  result_json TEXT, failure TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS promises (
  id TEXT PRIMARY KEY, call_id TEXT, kind TEXT, due_at REAL, state TEXT, attempts INTEGER,
  payload_json TEXT, kept_at REAL, created_at REAL);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, call_id TEXT, channel TEXT, to_addr TEXT, body TEXT, status TEXT,
  provider_id TEXT, created_at REAL, meta_json TEXT);
CREATE TABLE IF NOT EXISTS records (
  kind TEXT, id TEXT, json TEXT, updated_at REAL, PRIMARY KEY (kind, id));
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, key TEXT, json TEXT, t REAL);
CREATE TABLE IF NOT EXISTS files (
  id TEXT PRIMARY KEY, kind TEXT, owner TEXT, path TEXT, mime TEXT, bytes INTEGER,
  created_at REAL, meta_json TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def _j(v: Any) -> str:
    return json.dumps(v, default=str, separators=(",", ":"))


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(operations)")}
            if "fingerprint" not in columns:
                self.db.execute("ALTER TABLE operations ADD COLUMN fingerprint TEXT")
            if path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")

    def _x(self, sql: str, args: Iterable = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.db.execute(sql, tuple(args))

    def _all(self, sql: str, args: Iterable = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, tuple(args)).fetchall()]

    # ------------------------------------------------------------ calls and transcripts
    def start_call(self, call_id: str, tenant: str, channel: str, caller: str = "") -> None:
        self._x("INSERT OR IGNORE INTO calls (id, tenant, channel, caller, started_at) "
                "VALUES (?,?,?,?,?)", (call_id, tenant, channel, caller, time.time()))

    def end_call(self, call_id: str, outcome: str, summary: str = "") -> None:
        self._x("UPDATE calls SET ended_at=?, outcome=?, summary=? WHERE id=? AND "
                "ended_at IS NULL", (time.time(), outcome, summary, call_id))

    def save_state(self, call_id: str, state: dict) -> None:
        self._x("UPDATE calls SET state_json=? WHERE id=?", (_j(state), call_id))

    def call(self, call_id: str) -> dict | None:
        rows = self._all("SELECT * FROM calls WHERE id=?", (call_id,))
        return rows[0] if rows else None

    def calls(self, limit: int = 50, tenant: str | None = None) -> list[dict]:
        if tenant:
            return self._all("SELECT * FROM calls WHERE tenant=? ORDER BY started_at DESC "
                             "LIMIT ?", (tenant, limit))
        return self._all("SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,))

    def add_turn(self, call_id: str, n: int, who: str, text: str, speech: str = "",
                 meta: dict | None = None) -> None:
        self._x("INSERT INTO turns VALUES (?,?,?,?,?,?,?)",
                (call_id, n, time.time(), who, text, speech, _j(meta or {})))

    def transcript(self, call_id: str) -> list[dict]:
        rows = self._all("SELECT * FROM turns WHERE call_id=? ORDER BY rowid", (call_id,))
        for r in rows:
            r["meta"] = json.loads(r.pop("meta_json") or "{}")
        return rows

    # ------------------------------------------------------------ trace
    def add_span(self, call_id: str, turn: int, layer: str, name: str, start_ms: float,
                 end_ms: float, meta: dict | None = None) -> None:
        self._x("INSERT INTO spans VALUES (?,?,?,?,?,?,?)",
                (call_id, turn, layer, name, start_ms, end_ms, _j(meta or {})))

    def spans(self, call_id: str) -> list[dict]:
        rows = self._all("SELECT * FROM spans WHERE call_id=? ORDER BY start_ms", (call_id,))
        for r in rows:
            r["meta"] = json.loads(r.pop("meta_json") or "{}")
        return rows

    # ------------------------------------------------------------ operations and promises
    def op_get(self, op_id: str) -> dict | None:
        rows = self._all("SELECT * FROM operations WHERE id=?", (op_id,))
        if not rows:
            return None
        r = rows[0]
        r["terms"] = json.loads(r.pop("terms_json") or "{}")
        r["result"] = json.loads(r.pop("result_json") or "null")
        return r

    def op_put(self, op_id: str, call_id: str, tool: str, terms: dict, state: str,
               result: Any = None, failure: str | None = None,
               fingerprint: str | None = None) -> None:
        now = time.time()
        self._x("INSERT INTO operations (id,call_id,tool,terms_json,state,result_json,failure,"
                "created_at,updated_at,fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE "
                "SET state=excluded.state, result_json=excluded.result_json, "
                "failure=excluded.failure, updated_at=excluded.updated_at",
                (op_id, call_id, tool, _j(terms), state, _j(result), failure, now, now,
                 fingerprint))

    def ops(self, call_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM operations" + (" WHERE call_id=?" if call_id else "") + \
              " ORDER BY created_at"
        rows = self._all(sql, (call_id,) if call_id else ())
        for r in rows:
            r["terms"] = json.loads(r.pop("terms_json") or "{}")
            r["result"] = json.loads(r.pop("result_json") or "null")
        return rows

    def promise_put(self, pid: str, call_id: str, kind: str, due_at: float, state: str,
                    attempts: int, payload: dict, kept_at: float | None = None) -> None:
        self._x("INSERT INTO promises VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE "
                "SET state=excluded.state, attempts=excluded.attempts, "
                "kept_at=excluded.kept_at, payload_json=excluded.payload_json",
                (pid, call_id, kind, due_at, state, attempts, _j(payload), kept_at,
                 time.time()))

    def promises(self, state: str | None = None, call_id: str | None = None) -> list[dict]:
        where, args = [], []
        if state:
            where.append("state=?")
            args.append(state)
        if call_id:
            where.append("call_id=?")
            args.append(call_id)
        sql = "SELECT * FROM promises" + (" WHERE " + " AND ".join(where) if where else "") + \
              " ORDER BY due_at"
        rows = self._all(sql, args)
        for r in rows:
            r["payload"] = json.loads(r.pop("payload_json") or "{}")
        return rows

    # ------------------------------------------------------------ messages on other channels
    def add_message(self, mid: str, call_id: str | None, channel: str, to: str, body: str,
                    status: str, provider_id: str = "", meta: dict | None = None) -> None:
        self._x("INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?,?,?)",
                (mid, call_id, channel, to, body, status, provider_id, time.time(),
                 _j(meta or {})))

    def messages(self, call_id: str | None = None, to: str | None = None,
                 limit: int = 100) -> list[dict]:
        where, args = [], []
        if call_id:
            where.append("call_id=?")
            args.append(call_id)
        if to:
            where.append("to_addr=?")
            args.append(to)
        sql = "SELECT * FROM messages" + (" WHERE " + " AND ".join(where) if where else "") + \
              " ORDER BY created_at DESC LIMIT ?"
        rows = self._all(sql, args + [limit])
        for r in rows:
            r["meta"] = json.loads(r.pop("meta_json") or "{}")
        return rows

    # ------------------------------------------------------------ records and events
    def put(self, kind: str, rid: str, obj: dict) -> None:
        self._x("INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(kind, id) DO UPDATE SET "
                "json=excluded.json, updated_at=excluded.updated_at",
                (kind, rid, _j(obj), time.time()))

    def insert(self, kind: str, rid: str, obj: dict) -> bool:
        """Write once: False if the id already exists (the conditional write)."""
        try:
            self._x("INSERT INTO records VALUES (?,?,?,?)", (kind, rid, _j(obj), time.time()))
            return True
        except sqlite3.IntegrityError:
            return False

    def get(self, kind: str, rid: str) -> dict | None:
        rows = self._all("SELECT json FROM records WHERE kind=? AND id=?", (kind, rid))
        return json.loads(rows[0]["json"]) if rows else None

    def all(self, kind: str) -> list[dict]:
        return [json.loads(r["json"]) for r in
                self._all("SELECT json FROM records WHERE kind=? ORDER BY id", (kind,))]

    def clear_records(self) -> int:
        """Delete every business record: the calendar, the claims. Calls, operations, and messages
        stay, so a reset never hides what happened."""
        return self._x("DELETE FROM records").rowcount

    def count(self, kind: str) -> int:
        return self._all("SELECT COUNT(*) AS n FROM records WHERE kind=?", (kind,))[0]["n"]

    def event(self, kind: str, key: str, data: dict) -> int:
        cur = self._x("INSERT INTO events (kind, key, json, t) VALUES (?,?,?,?)",
                      (kind, key, _j(data), time.time()))
        return cur.lastrowid

    def events(self, kind: str | None = None, key: str | None = None) -> list[dict]:
        where, args = [], []
        if kind:
            where.append("kind=?")
            args.append(kind)
        if key:
            where.append("key=?")
            args.append(key)
        sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "") + \
              " ORDER BY seq"
        rows = self._all(sql, args)
        for r in rows:
            r["data"] = json.loads(r.pop("json") or "{}")
        return rows

    # ------------------------------------------------------------ files and settings
    def add_file(self, fid: str, kind: str, owner: str, path: str, mime: str, size: int,
                 meta: dict | None = None) -> None:
        self._x("INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",
                (fid, kind, owner, path, mime, size, time.time(), _j(meta or {})))

    def files(self, owner: str | None = None, kind: str | None = None) -> list[dict]:
        where, args = [], []
        if owner:
            where.append("owner=?")
            args.append(owner)
        if kind:
            where.append("kind=?")
            args.append(kind)
        sql = "SELECT * FROM files" + (" WHERE " + " AND ".join(where) if where else "") + \
              " ORDER BY created_at"
        rows = self._all(sql, args)
        for r in rows:
            r["meta"] = json.loads(r.pop("meta_json") or "{}")
        return rows

    def file(self, fid: str) -> dict | None:
        rows = self._all("SELECT * FROM files WHERE id=?", (fid,))
        if not rows:
            return None
        rows[0]["meta"] = json.loads(rows[0].pop("meta_json") or "{}")
        return rows[0]

    def update_file_meta(self, fid: str, meta: dict) -> None:
        self._x("UPDATE files SET meta_json=? WHERE id=?", (_j(meta), fid))

    def setting(self, key: str, default: str | None = None) -> str | None:
        rows = self._all("SELECT value FROM settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self._x("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value", (key, value))
