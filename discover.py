#!/usr/bin/env python3
"""
Discovery mode — lists your current Telegram chats/channels
so you can pick which ones to monitor without guessing usernames.

Usage: python scripts/discover.py
"""

import asyncio
import yaml
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'credentials.yaml')
SOURCES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'sources.yaml')


def load_credentials():
    with open(CREDENTIALS_PATH) as f:
        return yaml.safe_load(f)


async def discover():
    from telethon import TelegramClient
    from telethon.tl.types import Channel, Chat

    creds = load_credentials()
    client = TelegramClient(
        os.path.join(os.path.dirname(__file__), '..', 'data', 'jobbot.session'),
        creds['api_id'], creds['api_hash']
    )

    await client.start()
    print("\n📋 Your Telegram channels and groups:\n")
    print(f"{'#':<4} {'Type':<12} {'Username':<30} {'Title'}")
    print("-" * 75)

    channels = []
    idx = 1
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, (Channel, Chat)):
            uname = getattr(entity, 'username', None) or f"id:{entity.id}"
            etype = "channel" if getattr(entity, 'broadcast', False) else "group"
            print(f"{idx:<4} {etype:<12} {uname:<30} {dialog.name}")
            channels.append({'idx': idx, 'username': uname, 'title': dialog.name, 'type': etype})
            idx += 1

    print("\n")
    raw = input("Enter numbers to add to sources.yaml (comma-separated, e.g. 1,3,5): ").strip()
    if not raw:
        print("Nothing selected.")
        await client.disconnect()
        return

    selected_idxs = {int(x.strip()) for x in raw.split(',') if x.strip().isdigit()}
    selected = [c for c in channels if c['idx'] in selected_idxs]

    # Load existing sources
    with open(SOURCES_PATH) as f:
        sources = yaml.safe_load(f)

    existing = set(sources.get('channels', []))
    added = []
    for ch in selected:
        uname = ch['username']
        if uname.startswith('id:'):
            print(f"  ⚠️  {ch['title']} has no public username — skipping (use ID-based monitoring manually)")
            continue
        if uname not in existing:
            sources.setdefault('channels', []).append(uname)
            added.append(uname)
            print(f"  ✅ Added: @{uname} ({ch['title']})")
        else:
            print(f"  ℹ️  Already in list: @{uname}")

    if added:
        with open(SOURCES_PATH, 'w') as f:
            yaml.dump(sources, f, default_flow_style=False, allow_unicode=True)
        print(f"\n💾 Saved {len(added)} new channel(s) to config/sources.yaml")
    else:
        print("\nNo new channels added.")

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(discover())
