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
import heapq
import sqlite3
from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from .catalog import Catalog

SNIPPET_LEN = 200
RRF_K = 60
CATALOG_KINDS = ('post', 'comment', 'message', 'event', 'media', 'reaction',
                 'document')
CATALOG_SOURCES = ('facebook', 'document')

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

def _email_where(senders, after, before, disabled_accounts=None):
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
    if disabled_accounts:
        values = sorted(disabled_accounts)
        placeholders = ','.join('?' for _ in values)
        clauses.append(
            '(NOT EXISTS (SELECT 1 FROM origins o WHERE o.hash=m.hash) OR EXISTS '
            '(SELECT 1 FROM origins o WHERE o.hash=m.hash AND o.account NOT IN ('
            + placeholders + ')))')
        params.extend(values)
    return (' AND ' + ' AND '.join(clauses)) if clauses else '', params

def _disabled_sources(root):
    """Accounts and catalog source types explicitly disabled for new ingestion."""
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        return set(), set()
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    try:
        rows = conn.execute(
            "SELECT source, source_key FROM source_settings WHERE disabled_at IS NOT NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return ({key for source, key in rows if source == 'email'},
            {key for source, key in rows if source == 'catalog'})

def _email_count(root, query, senders=None, after=None, before=None,
                 disabled_accounts=None):
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    try:
        extra, params = _email_where(senders, after, before, disabled_accounts)
        sql = ('SELECT count(*) FROM search JOIN messages m ON m.hash = search.hash '
               f'WHERE search MATCH ?{extra}')
        try:
            return conn.execute(sql, (query, *params)).fetchone()[0]
        except sqlite3.OperationalError:
            return None
    finally:
        conn.close()

def _catalog_count(root, source_type, query, senders=None, kinds=None,
                   after=None, before=None):
    catalog = Catalog(root)
    try:
        return catalog.count_ranked(query, source_type, actor=senders,
                                    kinds=kinds, after=after, before=before)
    finally:
        catalog.close()

def _matches(item, senders, kinds, tagged):
    if senders and item['actor'] not in senders:
        return False
    if kinds and item['kind'] not in kinds:
        return False
    if tagged is not None and item['source'] == 'email' and item['id'] not in tagged:
        return False
    return True

def _public(item):
    return {'source': item['source'], 'id': item['id'], 'kind': item['kind'],
            'title': item['title'], 'actor': item['actor'], 'date': item['date'],
            'snippet': item['snippet']}

def _stream_key(item):
    return (-1.0 / (RRF_K + item['_rank'] + 1),
            -(item['_timestamp'] or 0), item['source'], item['id'])

class _RankedStream:
    """One index's post-filter matches in rank order, pulled lazily.

    Rows are fetched in bounded batches from a single read-only connection, so
    the merge never materializes the full match set in Python memory.
    """

    def __init__(self, conn, sql, params, mapper, accept, cancel=None):
        self._conn = conn
        self._cancel = cancel
        self._mapper = mapper
        self._accept = accept
        self._last_id = None
        self._rank = 0
        self._closed = False
        self._rows = deque()
        try:
            self._cursor = conn.execute(sql, params)
        except sqlite3.OperationalError:
            self._cursor = None
            self.close()

    def __iter__(self):
        return self

    def __next__(self):
        while not self._closed:
            if self._cancel is not None and self._cancel.is_set():
                self.close()
                raise StopIteration
            if not self._rows:
                try:
                    self._rows.extend(self._cursor.fetchmany(200))
                except sqlite3.OperationalError:
                    self.close()
                    raise StopIteration
                if not self._rows:
                    self.close()
                    raise StopIteration
            item, stamp = self._mapper(self._rows.popleft())
            if item['id'] == self._last_id:
                continue
            self._last_id = item['id']
            if not self._accept(item, stamp):
                continue
            item['_rank'] = self._rank
            item['_timestamp'] = stamp
            self._rank += 1
            return item
        raise StopIteration

    def close(self):
        if not self._closed:
            self._closed = True
            self._rows.clear()
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

def _email_stream(root, query, senders, kinds, tagged, after, before,
                  disabled_accounts, cancel):
    if kinds and 'message' not in kinds:
        return None
    if tagged is not None and not tagged:
        return None
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    extra, params = _email_where(senders, after, before, disabled_accounts)
    sql = ("SELECT search.hash, m.subject, m.sender, m.date, "
           "snippet(search, -1, '', '', '...', 24) "
           "FROM search JOIN messages m ON m.hash = search.hash "
           f"WHERE search MATCH ?{extra} ORDER BY bm25(search), m.hash")
    def mapper(row):
        return ({'source': 'email', 'id': row[0], 'kind': 'message',
                 'title': row[1] or '', 'actor': row[2] or '',
                 'date': row[3] or '', 'snippet': row[4] or ''},
                _timestamp(row[3]))
    def accept(item, stamp):
        if after is not None or before is not None:
            if stamp is None:
                return False
            if after is not None and stamp < after:
                return False
            if before is not None and stamp >= before:
                return False
        return _matches(item, senders, kinds, tagged)
    return _RankedStream(conn, sql, (query, *params), mapper, accept, cancel)

def _catalog_stream(root, query, senders, kinds, after, before, sources, cancel):
    path = Path(root) / 'catalog.sqlite3'
    if not path.is_file() or not sources:
        return None
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    source_clause = ','.join('?' for _ in sources)
    clauses = [f'r.source_type IN ({source_clause})', 'record_search MATCH ?']
    params = [*sources, query]
    if senders:
        clause, values = _in_clause('r.actor', senders)
        clauses.append(clause)
        params.extend(values)
    if kinds:
        clause, values = _in_clause('r.record_kind', kinds)
        clauses.append(clause)
        params.extend(values)
    if after is not None:
        clauses.append('r.occurred_at>=?')
        params.append(datetime.fromtimestamp(after, timezone.utc).isoformat())
    if before is not None:
        clauses.append('r.occurred_at<?')
        params.append(datetime.fromtimestamp(before, timezone.utc).isoformat())
    sql = ('SELECT r.record_id, r.source_type, r.source_key, r.record_kind, r.actor, '
           "r.occurred_at, r.body, snippet(record_search, -1, '', '', '...', 32) "
           'FROM records r JOIN record_search ON record_search.rowid = r.rowid '
           'WHERE ' + ' AND '.join(clauses) +
           ' ORDER BY bm25(record_search), r.record_id')
    def mapper(row):
        return ({'source': row[1], 'id': row[0], 'kind': row[3],
                 'title': row[2] or '', 'actor': row[4] or '',
                 'date': row[5] or '',
                 'snippet': (row[7] or row[6] or '')[:SNIPPET_LEN]},
                _timestamp(row[5]))
    def accept(item, stamp):
        if after is not None or before is not None:
            if stamp is None:
                return False
            if after is not None and stamp < after:
                return False
            if before is not None and stamp >= before:
                return False
        return _matches(item, senders, kinds, None)
    return _RankedStream(conn, sql, tuple(params), mapper, accept, cancel)

def search_unified_page(root, query, offset=0, limit=100,
                        sources=('email', 'facebook', 'document'),
                        after=None, before=None, senders=None, kinds=None, tags=None,
                        exclude_disabled=False, cancel=None):
    """Return one page of fused results ranked over the complete match sets.

    Source indexes are streamed in rank order and merged lazily, so results
    beyond any fixed candidate ceiling remain reachable without materializing
    the archive in memory. Filters and disabled-source rules are applied before
    a record receives its rank. `cancel` is an optional event-like object with
    an `is_set()` method; a cancelled request returns its partial page flagged
    `cancelled` rather than pretending the result set was complete.
    """
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 5000))
    senders = _normalize(senders)
    kinds = _normalize(kinds)
    tags = _normalize(tags)
    if not isinstance(query, str) or not query.strip():
        return {'items': [], 'has_more': False, 'scanned': 0, 'cancelled': False}
    if cancel is not None and cancel.is_set():
        return {'items': [], 'has_more': False, 'scanned': 0, 'cancelled': True}
    disabled_accounts, disabled_catalog = (
        _disabled_sources(root) if exclude_disabled else (set(), set()))
    tagged = _tagged_hashes(root, tags) if tags else None
    catalog_kinds = [kind for kind in kinds if kind in CATALOG_KINDS] if kinds else None
    catalog_sources = [source for source in sources if source in CATALOG_SOURCES
                       and source not in disabled_catalog]
    streams = []
    if 'email' in sources:
        stream = _email_stream(root, query, senders, kinds, tagged, after, before,
                               disabled_accounts, cancel)
        if stream is not None:
            streams.append(stream)
    if catalog_sources and tags is None and (not kinds or catalog_kinds):
        stream = _catalog_stream(root, query, senders, catalog_kinds, after, before,
                                 catalog_sources, cancel)
        if stream is not None:
            streams.append(stream)
    heap = []
    page = []
    scanned = 0
    has_more = False
    try:
        for index, stream in enumerate(streams):
            try:
                item = next(stream)
            except StopIteration:
                continue
            heapq.heappush(heap, (_stream_key(item), index, item, stream))
        if cancel is not None and cancel.is_set():
            return {'items': [], 'has_more': False, 'scanned': 0, 'cancelled': True}
        while heap:
            if cancel is not None and cancel.is_set():
                return {'items': page, 'has_more': True, 'scanned': scanned,
                        'cancelled': True}
            _, index, item, stream = heapq.heappop(heap)
            if scanned >= offset:
                if len(page) < limit:
                    page.append(_public(item))
                else:
                    has_more = True
                    break
            scanned += 1
            try:
                nxt = next(stream)
            except StopIteration:
                continue
            heapq.heappush(heap, (_stream_key(nxt), index, nxt, stream))
        cancelled = cancel is not None and cancel.is_set()
        return {'items': page, 'has_more': has_more or cancelled, 'scanned': scanned,
                'cancelled': cancelled}
    finally:
        for stream in streams:
            stream.close()

def search_unified(root, query, limit=100, sources=('email', 'facebook', 'document'),
                   after=None, before=None, senders=None, kinds=None, tags=None,
                   exclude_disabled=False):
    """Fused, filtered search. `tags` matches any listed tag (email only).

    This compatibility wrapper returns the first `limit` results. Paged
    callers should use `search_unified_page` so later results remain reachable.
    With `exclude_disabled`, records belonging only to disabled email accounts
    or disabled catalog source types are omitted. Messages shared with an
    enabled account, and messages imported from `.eml` files, remain visible.
    """
    return search_unified_page(
        root, query, offset=0, limit=limit, sources=sources, after=after,
        before=before, senders=senders, kinds=kinds, tags=tags,
        exclude_disabled=exclude_disabled)['items']

def search_unified_count(root, query, sources=('email', 'facebook', 'document'),
                         after=None, before=None, senders=None, kinds=None, tags=None,
                         exclude_disabled=False):
    """Exact total across sources, or None when a tag filter makes it inexact."""
    senders = _normalize(senders)
    kinds = _normalize(kinds)
    tags = _normalize(tags)
    if tags:
        return None
    disabled_accounts, disabled_catalog = (
        _disabled_sources(root) if exclude_disabled else (set(), set()))
    total = 0
    if 'email' in sources and (not kinds or 'message' in kinds):
        count = _email_count(root, query, senders, after, before, disabled_accounts)
        if count is None:
            return None
        total += count
    catalog_kinds = [kind for kind in kinds if kind in CATALOG_KINDS] if kinds else None
    catalog_sources = [source for source in sources if source in CATALOG_SOURCES
                       and source not in disabled_catalog]
    if catalog_sources and (not kinds or catalog_kinds):
        for source in catalog_sources:
            count = _catalog_count(root, source, query, senders, catalog_kinds,
                                   after, before)
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
