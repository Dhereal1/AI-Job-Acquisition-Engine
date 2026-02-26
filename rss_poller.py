#!/usr/bin/env python3
"""
RSS feed poller — runs alongside bot.py or standalone.
Polls configured RSS feeds and sends matches to Saved Messages.

Usage: python scripts/rss_poller.py
"""

import asyncio
import sqlite3
import yaml
import os
import sys
import hashlib
import logging
from datetime import datetime

import feedparser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from matcher import score_message, build_draft, load_config
from scripts.init_db import init_db, DB_PATH

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [RSS] %(message)s')

BASE = os.path.join(os.path.dirname(__file__), '..')
SOURCES_PATH = os.path.join(BASE, 'config', 'sources.yaml')
TEMPLATES_PATH = os.path.join(BASE, 'config', 'templates.yaml')
CREDENTIALS_PATH = os.path.join(BASE, 'config', 'credentials.yaml')


def load_sources():
    with open(SOURCES_PATH) as f:
        return yaml.safe_load(f)

def load_templates():
    with open(TEMPLATES_PATH) as f:
        return yaml.safe_load(f)

def load_credentials():
    with open(CREDENTIALS_PATH) as f:
        return yaml.safe_load(f)

def is_seen(msg_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM seen_ids WHERE message_id=?", (msg_id,)).fetchone()
    conn.close()
    return row is not None

def mark_seen(msg_id, source):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO seen_ids(message_id, source) VALUES(?,?)", (msg_id, source))
    conn.commit()
    conn.close()

def save_message(msg_id, source, date, text, score, matched, permalink, draft):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO messages
        (message_id, source, source_type, date, text, score, matched_keywords, permalink, draft)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (msg_id, source, 'rss', date, text, score, ','.join(matched), permalink, draft))
    conn.commit()
    conn.close()


async def poll_feeds(client, profile, templates):
    sources = load_sources()
    feeds = sources.get('rss_feeds', [])
    interval = sources.get('rss_interval', 1800)

    thresholds = profile.get('thresholds', {})
    notify_threshold = thresholds.get('notify', 14)
    strong_threshold = thresholds.get('strong', 22)

    while True:
        for feed_cfg in feeds:
            url = feed_cfg['url']
            name = feed_cfg.get('name', url)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                    link = entry.get('link', '')
                    uid = hashlib.md5(link.encode()).hexdigest()
                    msg_id = f"rss_{name}_{uid}"

                    if is_seen(msg_id):
                        continue
                    mark_seen(msg_id, name)

                    score, matched, negs = score_message(text, profile)
                    if score < notify_threshold:
                        continue

                    draft = build_draft(text, matched, profile, templates)
                    save_message(msg_id, name, str(datetime.now()), text, score, matched, link, draft)

                    emoji = "🔥" if score >= strong_threshold else "✅"
                    matched_str = ", ".join(f"`{k}`" for k in matched[:8])
                    notification = (
                        f"{emoji} **[RSS] Job Match** | Score: {score}\n"
                        f"📍 Source: {name}\n"
                        f"🎯 Keywords: {matched_str}\n\n"
                        f"📝 {text[:300]}...\n"
                        f"🔗 {link}\n\n"
                        f"---\n💬 **Draft:**\n{draft}"
                    )
                    await client.send_message('me', notification, parse_mode='markdown')
                    log.info(f"📬 RSS match: score={score} source={name} matched={matched}")

            except Exception as e:
                log.error(f"RSS error ({name}): {e}")

        log.info(f"RSS poll done. Next in {interval//60}min.")
        await asyncio.sleep(interval)


async def main():
    from telethon import TelegramClient
    init_db()
    creds = load_credentials()
    profile = load_config()
    templates = load_templates()

    client = TelegramClient(
        os.path.join(BASE, 'data', 'jobbot.session'),
        creds['api_id'], creds['api_hash']
    )
    await client.start()
    log.info("RSS poller started.")
    await poll_feeds(client, profile, templates)


if __name__ == '__main__':
    asyncio.run(main())
