# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Unified search across email and source-independent records.

Source-specific indexes rank their own matches (FTS5 bm25); the two ranked
lists are then fused with reciprocal rank fusion, so a result's position
reflects agreement between indexes rather than incomparable raw scores.
Snippets are plain text taken from the stored record, never from a model.
"""
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from catalog import Catalog

SNIPPET_LEN = 200
RRF_K = 60

def _timestamp(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        try:
            parsed = datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.timestamp()
    except (OverflowError, OSError):
        return None

def _email_search(root, query, limit):
    """Email matches, ranked by the FTS5 bm25 score (best first)."""
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    try:
        try:
            rows = conn.execute(
                "SELECT search.hash, m.subject, m.sender, m.date, "
                "snippet(search, -1, '', '', '...', 24) "
                "FROM search JOIN messages m ON m.hash = search.hash "
                "WHERE search MATCH ? ORDER BY bm25(search) LIMIT ?", (query, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{'source': 'email', 'id': r[0], 'kind': 'message',
                 'title': r[1] or '', 'actor': r[2] or '',
                 'date': r[3] or '', 'snippet': r[4] or ''} for r in rows]
    finally:
        conn.close()

def _facebook_search(root, query, limit):
    catalog = Catalog(root)
    try:
        rows = catalog.search_ranked(query, 'facebook', limit)
    finally:
        catalog.close()
    return [{'source': 'facebook', 'id': r[0], 'kind': r[2],
             'title': r[1] or '', 'actor': r[3] or '',
             'date': r[4] or '', 'snippet': (r[5] or '')[:SNIPPET_LEN]} for r in rows]

def _in_range(item, after, before):
    if after is None and before is None:
        return True
    stamp = _timestamp(item['date'])
    if stamp is None:
        return False
    if after is not None and stamp < after:
        return False
    if before is not None and stamp >= before:
        return False
    return True

def search_unified(root, query, limit=100, sources=('email', 'facebook'),
                   after=None, before=None):
    limit = max(1, min(int(limit), 5000))
    fetch = limit if after is None and before is None else min(5000, limit * 4)
    ranked = []
    if 'email' in sources:
        ranked.append(_email_search(root, query, fetch))
    if 'facebook' in sources:
        ranked.append(_facebook_search(root, query, fetch))
    results = []
    scores = {}
    for group in ranked:
        kept = [item for item in group if _in_range(item, after, before)]
        for rank, item in enumerate(kept):
            key = (item['source'], item['id'])
            if key not in scores:
                results.append(item)
                scores[key] = 0.0
            scores[key] += 1.0 / (RRF_K + rank + 1)
    results.sort(key=lambda item: (-scores[(item['source'], item['id'])],
                                   -(_timestamp(item['date']) or 0),
                                   item['source'], item['id']))
    return results[:limit]
