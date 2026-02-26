#!/usr/bin/env python3
"""Simple CLI dashboard for reviewing matched jobs."""

from __future__ import annotations

import argparse
from textwrap import shorten

from dashboard_data import DB_PATH, fetch_jobs, fetch_stats


def print_summary(stats: dict) -> None:
    print("\n=== Job Dashboard ===")
    print(f"DB: {DB_PATH}")
    print(
        f"Total: {stats['total']} | Pending: {stats['pending']} | Sent: {stats['sent']} "
        f"| Avg Score: {stats['avg_score']} | Top Source: {stats['top_source']}"
    )


def print_table(rows) -> None:
    if not rows:
        print("\nNo jobs found for the selected filters.")
        return

    print("\nID   Score  Status   Type      Source              Date                 Keywords")
    print("-" * 100)
    for row in rows:
        status = "pending" if row["notified"] == 0 else "sent"
        source = shorten(row["source"] or "-", width=18, placeholder="...")
        date = shorten(row["date"] or "-", width=20, placeholder="...")
        keywords = shorten(row["matched_keywords"] or "-", width=34, placeholder="...")
        print(
            f"{str(row['id']).ljust(4)} "
            f"{str(row['score']).ljust(6)} "
            f"{status.ljust(8)} "
            f"{(row['source_type'] or 'telegram').ljust(9)} "
            f"{source.ljust(18)} "
            f"{date.ljust(20)} "
            f"{keywords}"
        )


def print_details(rows) -> None:
    for row in rows:
        print("\n" + "=" * 100)
        print(f"#{row['id']} | score={row['score']} | source={row['source']} | type={row['source_type']}")
        print(f"Date: {row['date']}")
        print(f"Keywords: {row['matched_keywords'] or '-'}")
        if row["permalink"]:
            print(f"Link: {row['permalink']}")
        print(f"\nText:\n{row['text'] or '-'}")
        print(f"\nDraft:\n{row['draft'] or '-'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review matched jobs from SQLite")
    parser.add_argument("--min", type=int, default=0, help="Minimum score")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of rows")
    parser.add_argument(
        "--status",
        choices=["all", "pending", "sent"],
        default="all",
        help="Filter by notify status",
    )
    parser.add_argument(
        "--source-type",
        choices=["all", "telegram", "rss"],
        default="all",
        help="Filter source type",
    )
    parser.add_argument("--details", action="store_true", help="Show full text and draft")
    args = parser.parse_args()

    stats = fetch_stats(min_score=args.min, source_type=args.source_type)
    rows = fetch_jobs(
        min_score=args.min,
        limit=args.limit,
        status=args.status,
        source_type=args.source_type,
    )

    print_summary(stats)
    print_table(rows)
    if args.details:
        print_details(rows)


if __name__ == "__main__":
    main()
