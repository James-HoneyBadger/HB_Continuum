# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Unified keyword search across email and source-independent records.

Each result is a plain-text excerpt of the stored record text: snippets come
from the archive body or the catalog body, never from a model.
"""
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from catalog import Catalog

SNIPPET_LEN = 200

def _timestamp(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            parsed = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()

def _email_search(root, query, limit):
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    try:
        try:
            rows = conn.execute(
                "SELECT search.hash, m.subject, m.sender, m.date, "
                "snippet(search, -1, '', '', '...', 24) "
                "FROM search JOIN messages m ON m.hash = search.hash "
                "WHERE search MATCH ? LIMIT ?", (query, limit)).fetchall()
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
        rows = catalog.search_records(query, 'facebook', limit)
    finally:
        catalog.close()
    return [{'source': 'facebook', 'id': r[0], 'kind': r[2],
             'title': r[1] or '', 'actor': r[3] or '',
             'date': r[4] or '', 'snippet': (r[5] or '')[:SNIPPET_LEN]} for r in rows]

def search_unified(root, query, limit=100, sources=('email', 'facebook')):
    limit = max(1, min(int(limit), 5000))
    results = []
    if 'email' in sources:
        results.extend(_email_search(root, query, limit))
    if 'facebook' in sources:
        results.extend(_facebook_search(root, query, limit))
    results.sort(key=lambda item: (_timestamp(item['date']) is None, -(_timestamp(item['date']) or 0)))
    return results[:limit]
