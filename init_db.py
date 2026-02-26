#!/usr/bin/env python3
"""Initialize the SQLite database."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'jobs.db')

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
            notified        INTEGER DEFAULT 0,
            draft           TEXT,
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

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {os.path.abspath(DB_PATH)}")

if __name__ == '__main__':
    init_db()
