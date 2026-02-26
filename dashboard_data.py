#!/usr/bin/env python3
"""Shared data access helpers for job dashboards."""

from __future__ import annotations

import os
import sqlite3
from typing import Any


BASE_DIR = os.path.dirname(__file__)


def resolve_db_path() -> str:
    """Resolve the SQLite DB path across flat and scripts/ layouts."""
    env_path = os.getenv("JOBBOT_DB_PATH")
    if env_path:
        return env_path

    candidates = [
        os.path.join(BASE_DIR, "data", "jobs.db"),
        os.path.join(BASE_DIR, "..", "data", "jobs.db"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


DB_PATH = resolve_db_path()


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id       TEXT UNIQUE,
            source           TEXT NOT NULL,
            source_type      TEXT DEFAULT 'telegram',
            date             TEXT,
            text             TEXT,
            score            INTEGER DEFAULT 0,
            matched_keywords TEXT,
            permalink        TEXT,
            source_message_link TEXT,
            notified         INTEGER DEFAULT 0,
            draft            TEXT,
            draft_proposal   TEXT,
            draft_dm         TEXT,
            status           TEXT DEFAULT 'new',
            created_at       TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_score ON messages(score);
        CREATE INDEX IF NOT EXISTS idx_notified ON messages(notified);
        CREATE INDEX IF NOT EXISTS idx_date ON messages(date);
        """
    )
    existing = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(messages)").fetchall()
    }
    additions = {
        "status": "TEXT DEFAULT 'new'",
        "draft_proposal": "TEXT",
        "draft_dm": "TEXT",
        "source_message_link": "TEXT",
    }
    for col, sql_type in additions.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {sql_type}")


def fetch_stats(min_score: int = 0, source_type: str = "all") -> dict[str, Any]:
    where = ["score >= ?"]
    params: list[Any] = [min_score]

    if source_type != "all":
        where.append("source_type = ?")
        params.append(source_type)

    where_sql = " AND ".join(where)

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages WHERE {where_sql}", params
        ).fetchone()["c"]
        pending = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages WHERE {where_sql} AND notified = 0", params
        ).fetchone()["c"]
        sent = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages WHERE {where_sql} AND notified = 1", params
        ).fetchone()["c"]
        avg_score = conn.execute(
            f"SELECT AVG(score) AS a FROM messages WHERE {where_sql}", params
        ).fetchone()["a"]
        top_source = conn.execute(
            f"""
            SELECT source, COUNT(*) AS c
            FROM messages
            WHERE {where_sql}
            GROUP BY source
            ORDER BY c DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        conn.close()

    return {
        "total": int(total or 0),
        "pending": int(pending or 0),
        "sent": int(sent or 0),
        "avg_score": round(float(avg_score), 1) if avg_score is not None else 0.0,
        "top_source": top_source["source"] if top_source else "-",
    }


def fetch_jobs(
    min_score: int = 0,
    limit: int = 20,
    status: str = "all",
    source_type: str = "all",
) -> list[sqlite3.Row]:
    where = ["score >= ?"]
    params: list[Any] = [min_score]

    if status == "pending":
        where.append("notified = 0")
    elif status == "sent":
        where.append("notified = 1")

    if source_type != "all":
        where.append("source_type = ?")
        params.append(source_type)

    query = (
        "SELECT id, message_id, source, source_type, date, score, matched_keywords, permalink, text, draft, notified "
        "FROM messages "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY score DESC, id DESC "
        "LIMIT ?"
    )
    params.append(limit)

    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return rows


def set_notified(job_id: int, notified: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE messages SET notified = ? WHERE id = ?",
            (1 if notified else 0, job_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
