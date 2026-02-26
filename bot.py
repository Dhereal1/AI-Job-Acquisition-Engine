#!/usr/bin/env python3
"""
jobbot — Telegram job listener + scorer + notifier
Run: python bot.py

First time: it will ask for your phone number to log in via Telethon.
Session is saved locally as jobbot.session — never share this file.
"""

import asyncio
import sqlite3
import yaml
import os
import logging
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import Message

from matcher import score_message, build_draft, load_config
from scripts.init_db import init_db, DB_PATH

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('data/jobbot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── config paths ──────────────────────────────────────────────────────────────
BASE = os.path.dirname(__file__)
SOURCES_PATH = os.path.join(BASE, 'config', 'sources.yaml')
TEMPLATES_PATH = os.path.join(BASE, 'config', 'templates.yaml')
CREDENTIALS_PATH = os.path.join(BASE, 'config', 'credentials.yaml')


def load_sources() -> dict:
    with open(SOURCES_PATH) as f:
        return yaml.safe_load(f)


def load_templates() -> dict:
    with open(TEMPLATES_PATH) as f:
        return yaml.safe_load(f)


def load_credentials() -> dict:
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"\n❌ Missing {CREDENTIALS_PATH}\n"
            "Create it with:\n\n"
            "  api_id: 123456\n"
            "  api_hash: your_api_hash_here\n\n"
            "Get these free at: https://my.telegram.org/apps\n"
        )
    with open(CREDENTIALS_PATH) as f:
        return yaml.safe_load(f)


# ── database helpers ──────────────────────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_PATH)


def is_seen(message_id: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT 1 FROM seen_ids WHERE message_id=?", (message_id,)).fetchone()
    conn.close()
    return row is not None


def mark_seen(message_id: str, source: str):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO seen_ids(message_id, source) VALUES (?,?)", (message_id, source))
    conn.commit()
    conn.close()


def save_message(msg_id, source, date, text, score, matched, permalink, draft):
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO messages
        (message_id, source, source_type, date, text, score, matched_keywords, permalink, source_message_link, draft, draft_proposal, draft_dm, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        msg_id,
        source,
        'telegram',
        date,
        text,
        score,
        ','.join(matched),
        permalink,
        permalink,
        draft,
        draft,
        draft,
        'new',
    ))
    conn.commit()
    conn.close()


def mark_notified(msg_id: str):
    conn = get_db()
    conn.execute("UPDATE messages SET notified=1 WHERE message_id=?", (msg_id,))
    conn.commit()
    conn.close()


# ── notification formatter ────────────────────────────────────────────────────
def format_notification(score: int, source: str, permalink: str, text: str,
                         matched: list, draft: str, threshold_strong: int) -> str:
    emoji = "🔥" if score >= threshold_strong else "✅"
    excerpt = text[:400].replace('\n', ' ').strip()
    if len(text) > 400:
        excerpt += "..."

    matched_str = ", ".join(f"`{k}`" for k in matched[:8])

    msg = (
        f"{emoji} **Job Match** | Score: {score}\n"
        f"📍 Source: {source}\n"
        f"🎯 Keywords: {matched_str}\n\n"
        f"📝 **Excerpt:**\n{excerpt}\n"
    )
    if permalink:
        msg += f"\n🔗 [View original]({permalink})\n"

    msg += f"\n---\n💬 **Draft:**\n{draft}"
    return msg


# ── main listener ─────────────────────────────────────────────────────────────
async def main():
    creds = load_credentials()
    sources = load_sources()
    profile = load_config()
    templates = load_templates()

    thresholds = profile.get('thresholds', {})
    notify_threshold = thresholds.get('notify', 14)
    strong_threshold = thresholds.get('strong', 22)

    channels = sources.get('channels', [])

    client = TelegramClient('data/jobbot.session', creds['api_id'], creds['api_hash'])

    await client.start()
    me = await client.get_me()
    log.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
    log.info(f"📡 Monitoring {len(channels)} channels | notify≥{notify_threshold}, strong≥{strong_threshold}")

    async def handle(event, source_name):
        msg: Message = event.message
        if not msg.text or len(msg.text) < 50:
            return

        msg_id = f"{source_name}_{msg.id}"
        if is_seen(msg_id):
            return
        mark_seen(msg_id, source_name)

        score, matched, negs = score_message(msg.text, profile)

        if score < notify_threshold:
            return

        permalink = f"https://t.me/{source_name}/{msg.id}"
        draft = build_draft(msg.text, matched, profile, templates)

        save_message(
            msg_id, source_name,
            str(msg.date), msg.text,
            score, matched, permalink, draft
        )

        notification = format_notification(
            score, source_name, permalink,
            msg.text, matched, draft, strong_threshold
        )

        # Send to Saved Messages (= your own chat)
        await client.send_message('me', notification, parse_mode='markdown')
        mark_notified(msg_id)

        log.info(f"📬 Notified: score={score} source={source_name} matched={matched}")

    # Register handlers for each channel
    for ch in channels:
        @client.on(events.NewMessage(chats=ch))
        async def handler(event, _ch=ch):
            await handle(event, _ch)
        log.info(f"  👁  Watching: @{ch}")

    log.info("🚀 Bot is running. Press Ctrl+C to stop.\n")
    await client.run_until_disconnected()


if __name__ == '__main__':
    init_db()
    asyncio.run(main())
