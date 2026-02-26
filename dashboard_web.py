#!/usr/bin/env python3
"""Minimal FastAPI dashboard to review matched jobs."""

from __future__ import annotations

import html
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard_data import fetch_jobs, fetch_stats, set_notified


app = FastAPI(title="JobFinder Dashboard")


def _safe(value) -> str:
    return html.escape(str(value or ""))


def _status_badge(notified: int) -> str:
    if notified:
        return '<span style="color:#0f766e;font-weight:600;">sent</span>'
    return '<span style="color:#b45309;font-weight:600;">pending</span>'


@app.get("/", response_class=HTMLResponse)
def home(min_score: int = 0, limit: int = 50, status: str = "all", source_type: str = "all"):
    status = status if status in {"all", "pending", "sent"} else "all"
    source_type = source_type if source_type in {"all", "telegram", "rss"} else "all"
    limit = max(1, min(limit, 200))

    stats = fetch_stats(min_score=min_score, source_type=source_type)
    jobs = fetch_jobs(
        min_score=min_score,
        limit=limit,
        status=status,
        source_type=source_type,
    )

    filter_qs = urlencode({
        "min_score": min_score,
        "limit": limit,
        "status": status,
        "source_type": source_type,
    })

    rows = []
    for row in jobs:
        toggle_to = 0 if row["notified"] else 1
        toggle_label = "Mark Pending" if row["notified"] else "Mark Sent"
        toggle_link = f"/jobs/{row['id']}/toggle?value={toggle_to}&{filter_qs}"
        rows.append(
            "<tr>"
            f"<td>{row['id']}</td>"
            f"<td>{row['score']}</td>"
            f"<td>{_status_badge(row['notified'])}</td>"
            f"<td>{_safe(row['source_type'])}</td>"
            f"<td>{_safe(row['source'])}</td>"
            f"<td>{_safe(row['date'])}</td>"
            f"<td>{_safe(row['matched_keywords'])}</td>"
            f"<td><a href='{_safe(row['permalink'])}' target='_blank'>open</a></td>"
            f"<td><a href='/jobs/{row['id']}?{filter_qs}'>view</a></td>"
            f"<td><a href='{toggle_link}'>{toggle_label}</a></td>"
            "</tr>"
        )

    html_doc = f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>JobFinder Dashboard</title>
  <style>
    body {{ font-family: ui-sans-serif, -apple-system, Segoe UI, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
    h1 {{ margin: 0 0 16px; }}
    .stats {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 12px 0 20px; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; min-width: 120px; }}
    form {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
    input, select, button {{ padding: 7px 9px; border-radius: 8px; border: 1px solid #cbd5e1; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #f1f5f9; font-size: 14px; vertical-align: top; }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>JobFinder Dashboard</h1>
  <div class='stats'>
    <div class='card'><strong>Total</strong><br>{stats['total']}</div>
    <div class='card'><strong>Pending</strong><br>{stats['pending']}</div>
    <div class='card'><strong>Sent</strong><br>{stats['sent']}</div>
    <div class='card'><strong>Avg Score</strong><br>{stats['avg_score']}</div>
    <div class='card'><strong>Top Source</strong><br>{_safe(stats['top_source'])}</div>
  </div>

  <form method='get' action='/'>
    <label>Min Score <input name='min_score' type='number' value='{min_score}' /></label>
    <label>Limit <input name='limit' type='number' value='{limit}' min='1' max='200' /></label>
    <label>Status
      <select name='status'>
        <option value='all' {'selected' if status == 'all' else ''}>all</option>
        <option value='pending' {'selected' if status == 'pending' else ''}>pending</option>
        <option value='sent' {'selected' if status == 'sent' else ''}>sent</option>
      </select>
    </label>
    <label>Source
      <select name='source_type'>
        <option value='all' {'selected' if source_type == 'all' else ''}>all</option>
        <option value='telegram' {'selected' if source_type == 'telegram' else ''}>telegram</option>
        <option value='rss' {'selected' if source_type == 'rss' else ''}>rss</option>
      </select>
    </label>
    <button type='submit'>Apply</button>
  </form>

  <table>
    <thead>
      <tr><th>ID</th><th>Score</th><th>Status</th><th>Type</th><th>Source</th><th>Date</th><th>Keywords</th><th>Link</th><th>Details</th><th>Action</th></tr>
    </thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="10">No jobs found</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""
    return HTMLResponse(html_doc)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: int, min_score: int = 0, limit: int = 50, status: str = "all", source_type: str = "all"):
    jobs = fetch_jobs(min_score=0, limit=1000, status="all", source_type="all")
    row = next((r for r in jobs if r["id"] == job_id), None)
    if not row:
        return HTMLResponse("<h2>Job not found</h2><p><a href='/'>Back</a></p>", status_code=404)

    back_qs = urlencode(
        {
            "min_score": min_score,
            "limit": limit,
            "status": status,
            "source_type": source_type,
        }
    )

    body = f"""
    <html><head><meta charset='utf-8' /><title>Job {row['id']}</title>
    <style>
      body {{ font-family: ui-sans-serif, -apple-system, Segoe UI, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
      pre {{ white-space: pre-wrap; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }}
      a {{ color: #1d4ed8; text-decoration: none; }}
    </style></head><body>
    <p><a href='/?{back_qs}'>Back</a></p>
    <h2>Job #{row['id']} | score {row['score']} | {_safe(row['source'])}</h2>
    <p><strong>Date:</strong> {_safe(row['date'])}<br>
       <strong>Type:</strong> {_safe(row['source_type'])}<br>
       <strong>Status:</strong> {_status_badge(row['notified'])}<br>
       <strong>Keywords:</strong> {_safe(row['matched_keywords'])}</p>
    <p><a href='{_safe(row['permalink'])}' target='_blank'>Open original post</a></p>
    <h3>Message Text</h3>
    <pre>{_safe(row['text'])}</pre>
    <h3>Draft</h3>
    <pre>{_safe(row['draft'])}</pre>
    </body></html>
    """
    return HTMLResponse(body)


@app.get("/jobs/{job_id}/toggle")
def toggle_notified(
    job_id: int,
    value: int,
    min_score: int = 0,
    limit: int = 50,
    status: str = "all",
    source_type: str = "all",
):
    set_notified(job_id, 1 if value else 0)
    qs = urlencode(
        {
            "min_score": min_score,
            "limit": limit,
            "status": status,
            "source_type": source_type,
        }
    )
    return RedirectResponse(url=f"/?{qs}", status_code=302)


@app.get("/api/jobs")
def api_jobs(min_score: int = 0, limit: int = 20, status: str = "all", source_type: str = "all"):
    rows = fetch_jobs(min_score=min_score, limit=limit, status=status, source_type=source_type)
    return {
        "stats": fetch_stats(min_score=min_score, source_type=source_type),
        "jobs": [dict(r) for r in rows],
    }
