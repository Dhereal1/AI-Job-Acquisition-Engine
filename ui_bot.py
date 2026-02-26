#!/usr/bin/env python3
"""Owner-only Telegram UI bot for reviewing matched jobs."""

import asyncio
import os
import sqlite3
from pathlib import Path

import yaml
from telethon import Button, TelegramClient, events

from scripts.init_db import DB_PATH, init_db
from matcher import load_config

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "config" / "credentials.yaml"

STATUS_NEW = "new"
STATUS_VIEWED = "viewed"
STATUS_APPROVED = "approved"
STATUS_APPLIED = "applied"
STATUS_SKIPPED = "skipped"
VALID_STATUS = {STATUS_NEW, STATUS_VIEWED, STATUS_APPROVED, STATUS_APPLIED, STATUS_SKIPPED}

pending_edit: dict[int, int] = {}


def load_credentials() -> dict:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Missing credentials file: {CREDENTIALS_PATH}")
    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        creds = yaml.safe_load(f) or {}

    required = ["api_id", "api_hash", "bot_token", "owner_user_id"]
    missing = [k for k in required if k not in creds]
    if missing:
        raise ValueError(f"Missing required credentials keys: {', '.join(missing)}")
    return creds


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_jobs(limit: int = 8, min_score: int = 0, status: str | None = None):
    where = ["score >= ?"]
    params = [min_score]
    if status:
        where.append("status = ?")
        params.append(status)

    query = (
        "SELECT id, source, source_type, date, score, matched_keywords, status "
        "FROM messages "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY id DESC LIMIT ?"
    )
    params.append(limit)

    conn = get_db()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def get_job(job_id: int):
    conn = get_db()
    try:
        return conn.execute(
            """
            SELECT id, source, source_type, date, text, score, matched_keywords,
                   draft_proposal, draft_dm, status, source_message_link, permalink
            FROM messages WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    finally:
        conn.close()


def set_status(job_id: int, status: str) -> bool:
    if status not in VALID_STATUS:
        return False
    conn = get_db()
    try:
        cur = conn.execute("UPDATE messages SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_draft_proposal(job_id: int, draft: str) -> bool:
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE messages SET draft_proposal = ?, draft = ? WHERE id = ?",
            (draft, draft, job_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def build_job_text(row: sqlite3.Row) -> str:
    text = (row["text"] or "").strip()
    excerpt = text[:400] + ("..." if len(text) > 400 else "")
    proposal = (row["draft_proposal"] or row["draft_dm"] or "").strip()
    proposal_excerpt = proposal[:500] + ("..." if len(proposal) > 500 else "")

    return (
        f"Job #{row['id']} | score={row['score']} | status={row['status']}\n"
        f"source={row['source']} ({row['source_type']})\n"
        f"date={row['date']}\n"
        f"keywords={row['matched_keywords'] or '-'}\n\n"
        f"Text:\n{excerpt}\n\n"
        f"Draft Proposal:\n{proposal_excerpt or '-'}"
    )


def job_buttons(row: sqlite3.Row):
    job_id = row["id"]
    link = row["source_message_link"] or row["permalink"]
    action_row = [
        Button.inline("✅ Approve", data=f"set:{job_id}:{STATUS_APPROVED}".encode()),
        Button.inline("🗑 Skip", data=f"set:{job_id}:{STATUS_SKIPPED}".encode()),
        Button.inline("📌 Applied", data=f"set:{job_id}:{STATUS_APPLIED}".encode()),
    ]
    edit_row = [Button.inline("✍️ Edit proposal", data=f"edit:{job_id}".encode())]
    view_row = [Button.inline("🔄 Refresh", data=f"view:{job_id}".encode())]
    rows = [action_row, edit_row, view_row]
    if link:
        rows.append([Button.url("🔗 Open source", link)])
    return rows


def owner_only(user_id: int, owner_user_id: int) -> bool:
    return int(user_id) == int(owner_user_id)


async def main():
    init_db()
    creds = load_credentials()
    owner_user_id = int(creds["owner_user_id"])
    strong_threshold = (load_config().get("thresholds", {}) or {}).get("strong", 22)

    client = TelegramClient("data/ui_bot.session", creds["api_id"], creds["api_hash"])
    await client.start(bot_token=creds["bot_token"])

    @client.on(events.NewMessage(pattern=r"^/start$"))
    async def start_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            await event.reply("Not authorized.")
            return
        msg = (
            "Job UI Bot ready.\n\n"
            "Commands:\n"
            "/inbox - newest matches\n"
            f"/strong - score >= {strong_threshold}\n"
            "/stats - status counts"
        )
        await event.reply(msg)

    @client.on(events.NewMessage(pattern=r"^/inbox$"))
    async def inbox_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            await event.reply("Not authorized.")
            return

        rows = list_jobs(limit=8, min_score=0)
        if not rows:
            await event.reply("Inbox is empty.")
            return

        buttons = []
        lines = ["Newest matches:"]
        for row in rows:
            lines.append(f"#{row['id']} [{row['status']}] score={row['score']} {row['source']}")
            buttons.append([Button.inline(f"View #{row['id']}", data=f"view:{row['id']}".encode())])
        await event.reply("\n".join(lines), buttons=buttons)

    @client.on(events.NewMessage(pattern=r"^/strong$"))
    async def strong_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            await event.reply("Not authorized.")
            return

        rows = list_jobs(limit=8, min_score=strong_threshold)
        if not rows:
            await event.reply(f"No strong matches (score >= {strong_threshold}).")
            return

        buttons = []
        lines = [f"Strong matches (score >= {strong_threshold}):"]
        for row in rows:
            lines.append(f"#{row['id']} [{row['status']}] score={row['score']} {row['source']}")
            buttons.append([Button.inline(f"View #{row['id']}", data=f"view:{row['id']}".encode())])
        await event.reply("\n".join(lines), buttons=buttons)

    @client.on(events.NewMessage(pattern=r"^/stats$"))
    async def stats_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            await event.reply("Not authorized.")
            return

        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT COALESCE(status, 'new') AS status, COUNT(*) AS c FROM messages GROUP BY COALESCE(status, 'new')"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            await event.reply("No jobs in database yet.")
            return

        lines = ["Status counts:"]
        for row in rows:
            lines.append(f"- {row['status']}: {row['c']}")
        await event.reply("\n".join(lines))

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            await event.answer("Not authorized", alert=True)
            return

        data = event.data.decode("utf-8", errors="ignore")
        if data.startswith("view:"):
            job_id = int(data.split(":", 1)[1])
            row = get_job(job_id)
            if not row:
                await event.answer("Job not found", alert=True)
                return
            set_status(job_id, STATUS_VIEWED if row["status"] == STATUS_NEW else row["status"])
            row = get_job(job_id)
            await event.edit(build_job_text(row), buttons=job_buttons(row))
            await event.answer("Loaded")
            return

        if data.startswith("set:"):
            _, raw_id, status = data.split(":", 2)
            job_id = int(raw_id)
            ok = set_status(job_id, status)
            if not ok:
                await event.answer("Update failed", alert=True)
                return
            row = get_job(job_id)
            await event.edit(build_job_text(row), buttons=job_buttons(row))
            await event.answer(f"Status -> {status}")
            return

        if data.startswith("edit:"):
            job_id = int(data.split(":", 1)[1])
            pending_edit[event.sender_id] = job_id
            await event.respond(
                f"Send the new proposal text for job #{job_id}."
            )
            await event.answer("Awaiting new proposal text")
            return

        await event.answer("Unknown action", alert=True)

    @client.on(events.NewMessage)
    async def edit_capture_handler(event):
        if not owner_only(event.sender_id, owner_user_id):
            return
        if event.raw_text.startswith("/"):
            return

        job_id = pending_edit.get(event.sender_id)
        if not job_id:
            return

        new_text = (event.raw_text or "").strip()
        if not new_text:
            await event.reply("Empty text. Send the updated proposal content.")
            return

        if set_draft_proposal(job_id, new_text):
            pending_edit.pop(event.sender_id, None)
            row = get_job(job_id)
            await event.reply(
                f"Updated draft for job #{job_id}.",
                buttons=job_buttons(row),
            )
        else:
            await event.reply("Failed to update draft.")

    print("UI bot running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
