#!/usr/bin/env python3
"""
Review saved job matches from the database.
Usage:
  python scripts/review.py              # show top 20 matches
  python scripts/review.py --min 20     # only strong matches
  python scripts/review.py --limit 50   # more results
  python scripts/review.py --unnotified # only unnotified
"""

import sqlite3
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.init_db import DB_PATH


def review(min_score=0, limit=20, unnotified_only=False):
    conn = sqlite3.connect(DB_PATH)

    query = "SELECT id, source, date, score, matched_keywords, permalink, text, draft, notified FROM messages"
    conditions = [f"score >= {min_score}"]
    if unnotified_only:
        conditions.append("notified = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY score DESC LIMIT {limit}"

    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        print("No matches found.")
        return

    print(f"\n{'='*70}")
    print(f"  📋 Top Matches (min_score={min_score}, limit={limit})")
    print(f"{'='*70}\n")

    for row in rows:
        id_, source, date, score, matched, permalink, text, draft, notified = row
        status = "✉️  sent" if notified else "📥 pending"
        print(f"[#{id_}] Score: {score} | Source: @{source} | {status}")
        print(f"Date: {date}")
        print(f"Keywords: {matched}")
        if permalink:
            print(f"Link: {permalink}")
        print(f"\nExcerpt: {text[:300]}..." if text and len(text) > 300 else f"\nText: {text}")
        print(f"\n--- Draft ---\n{draft}")
        print(f"\n{'─'*70}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min', type=int, default=0, help='Minimum score')
    parser.add_argument('--limit', type=int, default=20, help='Max results')
    parser.add_argument('--unnotified', action='store_true', help='Only unnotified')
    args = parser.parse_args()
    review(args.min, args.limit, args.unnotified)


if __name__ == '__main__':
    main()
