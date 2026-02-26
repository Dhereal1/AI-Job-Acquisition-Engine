#!/usr/bin/env python3
"""Initialize the SQLite database."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'jobs.db')


def ensure_message_columns(conn: sqlite3.Connection):
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
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


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id      TEXT UNIQUE,
            source          TEXT NOT NULL,
            source_type     TEXT DEFAULT 'telegram',  -- telegram / rss
            date            TEXT,
            text            TEXT,
            score           INTEGER DEFAULT 0,
            matched_keywords TEXT,
            permalink       TEXT,
            source_message_link TEXT,
            notified        INTEGER DEFAULT 0,
            draft           TEXT,
            draft_proposal  TEXT,
            draft_dm        TEXT,
            status          TEXT DEFAULT 'new',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_score ON messages(score);
        CREATE INDEX IF NOT EXISTS idx_notified ON messages(notified);
        CREATE INDEX IF NOT EXISTS idx_date ON messages(date);

        CREATE TABLE IF NOT EXISTS seen_ids (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id  TEXT UNIQUE,
            source      TEXT
        );
    """)
    ensure_message_columns(conn)

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {os.path.abspath(DB_PATH)}")

if __name__ == '__main__':
    init_db()
