# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Unified search across email and source-independent records.

Source-specific indexes rank their own matches (FTS5 bm25); the ranked lists
are fused with reciprocal rank fusion, so a result's position reflects
agreement between indexes rather than incomparable raw scores. Snippets are
plain text taken from the stored record, never from a model.

Filters are applied in SQL where the schema supports them and re-checked in
Python as a guard. Exact totals are available unless a tag filter is used,
because tags live in the research overlay and are applied after ranking.
"""
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from .catalog import Catalog

SNIPPET_LEN = 200
RRF_K = 60
CATALOG_KINDS = ('post', 'comment', 'message', 'event', 'media', 'reaction')

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

def _normalize(values):
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    cleaned = [value for value in dict.fromkeys(values) if isinstance(value, str) and value]
    return cleaned or None

def _in_clause(column, values):
    return column + ' IN (' + ','.join('?' for _ in values) + ')', list(values)

def _tagged_hashes(root, tags):
    path = Path(root) / 'research.sqlite3'
    if not path.is_file():
        return set()
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    try:
        values = list(dict.fromkeys(tags))
        placeholders = ','.join('?' for _ in values)
        return {h for h, in conn.execute(
            f'SELECT DISTINCT hash FROM tags WHERE tag IN ({placeholders})', values)}
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()

def _email_where(senders, after, before):
    clauses = []
    params = []
    if senders:
        clause, values = _in_clause('m.sender', senders)
        clauses.append(clause)
        params.extend(values)
    if after is not None:
        clauses.append('m.sort_ts>=?')
        params.append(int(after))
    if before is not None:
        clauses.append('m.sort_ts<?')
        params.append(int(before))
    return (' AND ' + ' AND '.join(clauses)) if clauses else '', params

def _email_search(root, query, limit, senders=None, after=None, before=None):
    """Email matches, ranked by the FTS5 bm25 score (best first)."""
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    try:
        extra, params = _email_where(senders, after, before)
        sql = ("SELECT search.hash, m.subject, m.sender, m.date, "
               "snippet(search, -1, '', '', '...', 24) "
               "FROM search JOIN messages m ON m.hash = search.hash "
               f"WHERE search MATCH ?{extra} ORDER BY bm25(search) LIMIT ?")
        try:
            rows = conn.execute(sql, (query, *params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{'source': 'email', 'id': r[0], 'kind': 'message',
                 'title': r[1] or '', 'actor': r[2] or '',
                 'date': r[3] or '', 'snippet': r[4] or ''} for r in rows]
    finally:
        conn.close()

def _email_count(root, query, senders=None, after=None, before=None):
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    try:
        extra, params = _email_where(senders, after, before)
        sql = ('SELECT count(*) FROM search JOIN messages m ON m.hash = search.hash '
               f'WHERE search MATCH ?{extra}')
        try:
            return conn.execute(sql, (query, *params)).fetchone()[0]
        except sqlite3.OperationalError:
            return None
    finally:
        conn.close()

def _facebook_search(root, query, limit, senders=None, kinds=None, after=None, before=None):
    catalog = Catalog(root)
    try:
        rows = catalog.search_ranked(query, 'facebook', limit, actor=senders,
                                     kinds=kinds, after=after, before=before)
    finally:
        catalog.close()
    return [{'source': 'facebook', 'id': r[0], 'kind': r[2],
             'title': r[1] or '', 'actor': r[3] or '',
             'date': r[4] or '', 'snippet': (r[6] or r[5] or '')[:SNIPPET_LEN]}
            for r in rows]

def _facebook_count(root, query, senders=None, kinds=None, after=None, before=None):
    catalog = Catalog(root)
    try:
        return catalog.count_ranked(query, 'facebook', actor=senders,
                                    kinds=kinds, after=after, before=before)
    finally:
        catalog.close()

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

def _matches(item, senders, kinds, tagged):
    if senders and item['actor'] not in senders:
        return False
    if kinds and item['kind'] not in kinds:
        return False
    if tagged is not None and item['source'] == 'email' and item['id'] not in tagged:
        return False
    return True

def search_unified(root, query, limit=100, sources=('email', 'facebook'),
                   after=None, before=None, senders=None, kinds=None, tags=None):
    """Fused, filtered search. `tags` matches any listed tag (email only)."""
    limit = max(1, min(int(limit), 5000))
    senders = _normalize(senders)
    kinds = _normalize(kinds)
    tags = _normalize(tags)
    tagged = _tagged_hashes(root, tags) if tags else None
    fetch = limit if (after is None and before is None and not tags) else min(5000, limit * 4)
    ranked = []
    if 'email' in sources and (not kinds or 'message' in kinds):
        if tagged is None or tagged:
            ranked.append(_email_search(root, query, fetch, senders, after, before))
    catalog_kinds = [kind for kind in kinds if kind in CATALOG_KINDS] if kinds else None
    if 'facebook' in sources and tags is None:
        if not kinds or catalog_kinds:
            ranked.append(_facebook_search(root, query, fetch, senders, catalog_kinds,
                                           after, before))
    results = []
    scores = {}
    for group in ranked:
        kept = [item for item in group
                if _in_range(item, after, before) and _matches(item, senders, kinds, tagged)]
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

def search_unified_count(root, query, sources=('email', 'facebook'),
                         after=None, before=None, senders=None, kinds=None, tags=None):
    """Exact total across sources, or None when a tag filter makes it inexact."""
    senders = _normalize(senders)
    kinds = _normalize(kinds)
    tags = _normalize(tags)
    if tags:
        return None
    total = 0
    if 'email' in sources and (not kinds or 'message' in kinds):
        count = _email_count(root, query, senders, after, before)
        if count is None:
            return None
        total += count
    catalog_kinds = [kind for kind in kinds if kind in CATALOG_KINDS] if kinds else None
    if 'facebook' in sources and (not kinds or catalog_kinds):
        count = _facebook_count(root, query, senders, catalog_kinds, after, before)
        if count is None:
            return None
        total += count
    return total

def validate_query(root, query):
    """Return whether the FTS5 expression is accepted, with an explanation.

    Search currently treats a rejected expression as no matches. This check
    runs the expression against every available index without returning rows,
    so the UI can explain a syntax problem instead of showing an empty list.
    """
    if not isinstance(query, str) or not query.strip():
        return {'valid': False, 'message': 'Enter a non-empty search query.'}
    root = Path(root)
    errors = []
    tried = 0
    attempts = []
    if (root / 'archive.sqlite3').is_file():
        attempts.append(('archive.sqlite3', 'SELECT 1 FROM search WHERE search MATCH ? LIMIT 1'))
    if (root / 'catalog.sqlite3').is_file():
        attempts.append(('catalog.sqlite3',
                         'SELECT 1 FROM record_search WHERE record_search MATCH ? LIMIT 1'))
    if not attempts:
        return {'valid': False, 'message': 'This archive has no searchable index.'}
    for filename, sql in attempts:
        tried += 1
        conn = sqlite3.connect(str(root / filename), timeout=30)
        conn.execute('PRAGMA query_only=ON')
        try:
            conn.execute(sql, (query,)).fetchone()
            return {'valid': True, 'message': ''}
        except sqlite3.OperationalError as exc:
            errors.append(str(exc))
        finally:
            conn.close()
    message = errors[0] if errors else 'The query was rejected by the index.'
    return {'valid': False,
            'message': f'{message}. Use quotes for phrases, * for a prefix, and uppercase '
                       'AND/OR/NOT for boolean expressions.'}
