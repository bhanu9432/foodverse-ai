"""Tiny SQLite store: scan history (records) and the user's profile (settings)."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS records ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, "
            "created_at TEXT NOT NULL, data TEXT NOT NULL)"
        )
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind, created_at)")


def add_record(kind: str, data: dict) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with conn() as c:
        cur = c.execute(
            "INSERT INTO records(kind, created_at, data) VALUES (?,?,?)", (kind, now, json.dumps(data))
        )
        return cur.lastrowid


def list_records(kind: str | None = None, since: str | None = None, limit: int = 200) -> list[dict]:
    sql, args = "SELECT id, kind, created_at, data FROM records WHERE 1=1", []
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if since:
        sql += " AND created_at>=?"
        args.append(since)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [{"id": r["id"], "kind": r["kind"], "created_at": r["created_at"], "data": json.loads(r["data"])} for r in rows]


def delete_record(rec_id: int) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM records WHERE id=?", (rec_id,)).rowcount > 0


def get_setting(key: str, default=None):
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
