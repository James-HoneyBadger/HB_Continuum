# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Nested boolean search with explicit set semantics.

The advanced builder sends a tree of groups (`and`, `or`, `not`) and rules
(text, actor, kind, source, date, tag). Each rule is evaluated as a set of
record keys against the selected indexes, and groups combine those sets. A
`not` group is the complement of its child within the selected sources, so
negation is exact rather than a post-filter.

Results rank by the summed reciprocal rank of text rules, then newest
declared date. Snippets and titles come from stored records; nothing is
generated.
"""
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

MAX_DEPTH = 6
MAX_NODES = 100
MAX_CHILDREN = 20
MAX_VALUES = 50
MAX_TEXT = 500
MAX_LEAF_MATCHES = 200_000
RRF_K = 60
CATALOG_KINDS = ('post', 'comment', 'message', 'event', 'media', 'reaction')


def _strings(value, field):
    if isinstance(value, str):
        value = [part.strip() for part in value.split(',') if part.strip()]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f'{field} must be a non-empty list of strings')
    if len(value) > MAX_VALUES:
        raise ValueError(f'{field} accepts at most {MAX_VALUES} values')
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f'{field} must contain non-empty strings')
        if len(item) > 200:
            raise ValueError(f'{field} values must be 200 characters or fewer')
        cleaned.append(item.strip())
    return list(dict.fromkeys(cleaned))


def _epoch(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith(('Z', 'z')):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        try:
            parsed = parsedate_to_datetime(text)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.timestamp()
    except (OverflowError, OSError):
        return None


def normalize_query(tree):
    """Validate and copy a query tree. Raises ValueError with a usable message."""
    count = [0]

    def walk(raw, depth):
        count[0] += 1
        if count[0] > MAX_NODES:
            raise ValueError(f'query accepts at most {MAX_NODES} groups and rules')
        if depth > MAX_DEPTH:
            raise ValueError(f'query nesting is limited to {MAX_DEPTH} levels')
        if not isinstance(raw, dict):
            raise ValueError('each query node must be an object')
        node_type = raw.get('type')
        if node_type == 'group':
            op = raw.get('op')
            if op not in ('and', 'or', 'not'):
                raise ValueError('group op must be and, or or not')
            children = raw.get('children')
            if not isinstance(children, list) or not children:
                raise ValueError('every group needs at least one child')
            if len(children) > MAX_CHILDREN:
                raise ValueError(f'groups accept at most {MAX_CHILDREN} children')
            if op == 'not' and len(children) != 1:
                raise ValueError('a not group takes exactly one child')
            return {'type': 'group', 'op': op,
                    'children': [walk(child, depth + 1) for child in children]}
        if node_type != 'rule':
            raise ValueError('query nodes must be groups or rules')
        kind = raw.get('kind')
        if kind == 'text':
            value = raw.get('value')
            if not isinstance(value, str) or not value.strip():
                raise ValueError('a text rule needs a non-empty expression')
            if len(value) > MAX_TEXT:
                raise ValueError(f'a text rule is limited to {MAX_TEXT} characters')
            return {'type': 'rule', 'kind': 'text', 'value': value.strip()}
        if kind in ('actor', 'source'):
            values = _strings(raw.get('values'), f'{kind} rule')
            allowed = {'email', 'facebook'} if kind == 'source' else None
            if allowed is not None and any(value not in allowed for value in values):
                raise ValueError('source values must be email or facebook')
            return {'type': 'rule', 'kind': kind, 'values': values}
        if kind == 'kind':
            values = _strings(raw.get('values'), 'kind rule')
            allowed = set(CATALOG_KINDS) | {'message'}
            if any(value not in allowed for value in values):
                raise ValueError('kind rule contains an unsupported record kind')
            return {'type': 'rule', 'kind': 'kind', 'values': values}
        if kind == 'date':
            after = raw.get('after')
            before = raw.get('before')
            for name, value in (('after', after), ('before', before)):
                if value is not None and (not isinstance(value, int)
                                          or isinstance(value, bool)):
                    raise ValueError(f'date rule {name} must be a UTC epoch integer')
            if after is None and before is None:
                raise ValueError('a date rule needs after, before, or both')
            return {'type': 'rule', 'kind': 'date', 'after': after, 'before': before}
        if kind == 'tag':
            values = _strings(raw.get('values'), 'tag rule')
            mode = raw.get('mode', 'any')
            if mode not in ('any', 'all'):
                raise ValueError('tag rule mode must be any or all')
            return {'type': 'rule', 'kind': 'tag', 'values': values, 'mode': mode}
        raise ValueError('unknown rule kind: ' + repr(kind))

    return walk(tree, 0)


def _connect(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    return conn


def _all_email_ids(root):
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        return set()
    conn = _connect(path)
    try:
        return {row[0] for row in conn.execute('SELECT hash FROM messages')}
    finally:
        conn.close()


def _all_catalog_ids(root):
    path = Path(root) / 'catalog.sqlite3'
    if not path.is_file():
        return set()
    conn = _connect(path)
    try:
        return {row[0] for row in conn.execute(
            "SELECT record_id FROM records WHERE source_type='facebook'")}
    finally:
        conn.close()


def _has_not(node):
    if node['type'] == 'group':
        return node['op'] == 'not' or any(_has_not(child) for child in node['children'])
    return False


def _universe(root, sources):
    keys = set()
    if 'email' in sources:
        keys.update(('email', value) for value in _all_email_ids(root))
    if 'facebook' in sources:
        keys.update(('catalog', value) for value in _all_catalog_ids(root))
    return keys


def _text_rule(root, value, sources):
    matches = set()
    scores = {}
    syntax = ('Use quotes for phrases, * for a prefix, and uppercase AND/OR/NOT '
              'with parentheses for nesting.')
    if 'email' in sources:
        path = Path(root) / 'archive.sqlite3'
        if path.is_file():
            conn = _connect(path)
            try:
                rows = conn.execute(
                    'SELECT hash FROM search WHERE search MATCH ? ORDER BY bm25(search) '
                    'LIMIT ?', (value, MAX_LEAF_MATCHES + 1)).fetchall()
            except sqlite3.OperationalError as exc:
                raise ValueError(f'Email index rejected the text rule: {exc}. {syntax}') from None
            finally:
                conn.close()
            if len(rows) > MAX_LEAF_MATCHES:
                raise ValueError('A text rule matches too many email records; narrow it.')
            for rank, (digest,) in enumerate(rows):
                key = ('email', digest)
                matches.add(key)
                scores[key] = 1.0 / (RRF_K + rank + 1)
    if 'facebook' in sources:
        path = Path(root) / 'catalog.sqlite3'
        if path.is_file():
            conn = _connect(path)
            try:
                rows = conn.execute(
                    'SELECT r.record_id FROM records r JOIN record_search '
                    'ON record_search.rowid = r.rowid '
                    "WHERE r.source_type='facebook' AND record_search MATCH ? "
                    'ORDER BY bm25(record_search) LIMIT ?',
                    (value, MAX_LEAF_MATCHES + 1)).fetchall()
            except sqlite3.OperationalError as exc:
                raise ValueError(
                    f'Catalog index rejected the text rule: {exc}. {syntax}') from None
            finally:
                conn.close()
            if len(rows) > MAX_LEAF_MATCHES:
                raise ValueError('A text rule matches too many catalog records; narrow it.')
            for rank, (record_id,) in enumerate(rows):
                key = ('catalog', record_id)
                matches.add(key)
                scores[key] = 1.0 / (RRF_K + rank + 1)
    return matches, scores


def _actor_rule(root, values, sources):
    matches = set()
    placeholders = ','.join('?' for _ in values)
    if 'email' in sources:
        path = Path(root) / 'archive.sqlite3'
        if path.is_file():
            conn = _connect(path)
            try:
                matches.update(('email', row[0]) for row in conn.execute(
                    f'SELECT hash FROM messages WHERE sender IN ({placeholders})', values))
            finally:
                conn.close()
    if 'facebook' in sources:
        path = Path(root) / 'catalog.sqlite3'
        if path.is_file():
            conn = _connect(path)
            try:
                matches.update(('catalog', row[0]) for row in conn.execute(
                    'SELECT record_id FROM records WHERE source_type=? '
                    f'AND actor IN ({placeholders})', ('facebook', *values)))
            finally:
                conn.close()
    return matches


def _kind_rule(root, values, sources):
    matches = set()
    if 'email' in sources and 'message' in values:
        matches.update(('email', value) for value in _all_email_ids(root))
    catalog_kinds = [value for value in values if value in CATALOG_KINDS]
    if 'facebook' in sources and catalog_kinds:
        path = Path(root) / 'catalog.sqlite3'
        if path.is_file():
            placeholders = ','.join('?' for _ in catalog_kinds)
            conn = _connect(path)
            try:
                matches.update(('catalog', row[0]) for row in conn.execute(
                    'SELECT record_id FROM records WHERE source_type=? '
                    f'AND record_kind IN ({placeholders})', ('facebook', *catalog_kinds)))
            finally:
                conn.close()
    return matches


def _date_rule(root, after, before, sources):
    matches = set()
    if 'email' in sources:
        path = Path(root) / 'archive.sqlite3'
        if path.is_file():
            clauses = []
            params = []
            if after is not None:
                clauses.append('sort_ts>=?')
                params.append(int(after))
            if before is not None:
                clauses.append('sort_ts<?')
                params.append(int(before))
            conn = _connect(path)
            try:
                try:
                    rows = conn.execute(
                        'SELECT hash FROM messages WHERE ' + ' AND '.join(clauses), params)
                    matches.update(('email', row[0]) for row in rows)
                except sqlite3.OperationalError:
                    for digest, value in conn.execute('SELECT hash,date FROM messages'):
                        stamp = _epoch(value)
                        if stamp is None:
                            continue
                        if after is not None and stamp < after:
                            continue
                        if before is not None and stamp >= before:
                            continue
                        matches.add(('email', digest))
            finally:
                conn.close()
    if 'facebook' in sources:
        path = Path(root) / 'catalog.sqlite3'
        if path.is_file():
            conn = _connect(path)
            try:
                for record_id, value in conn.execute(
                        "SELECT record_id,occurred_at FROM records "
                        "WHERE source_type='facebook'"):
                    stamp = _epoch(value)
                    if stamp is None:
                        continue
                    if after is not None and stamp < after:
                        continue
                    if before is not None and stamp >= before:
                        continue
                    matches.add(('catalog', record_id))
            finally:
                conn.close()
    return matches


def _tag_rule(root, values, mode):
    path = Path(root) / 'research.sqlite3'
    if not path.is_file():
        return set()
    placeholders = ','.join('?' for _ in values)
    conn = _connect(path)
    try:
        try:
            rows = conn.execute(
                'SELECT hash, count(DISTINCT tag) FROM tags '
                f'WHERE tag IN ({placeholders}) GROUP BY hash', values).fetchall()
        except sqlite3.OperationalError:
            return set()
    finally:
        conn.close()
    required = len(values) if mode == 'all' else 1
    return {('email', digest) for digest, count in rows if count >= required}


def _evaluate(node, root, sources, universe):
    if node['type'] == 'group':
        op = node['op']
        if op == 'not':
            child, _ = _evaluate(node['children'][0], root, sources, universe)
            return universe - child, {}
        parts = [_evaluate(child, root, sources, universe) for child in node['children']]
        if op == 'and':
            matched = set.intersection(*(part[0] for part in parts))
        else:
            matched = set().union(*(part[0] for part in parts))
        scores = {}
        for _, part_scores in parts:
            for key, value in part_scores.items():
                if key in matched:
                    scores[key] = scores.get(key, 0.0) + value
        return matched, scores
    kind = node['kind']
    if kind == 'text':
        return _text_rule(root, node['value'], sources)
    if kind == 'actor':
        return _actor_rule(root, node['values'], sources), {}
    if kind == 'kind':
        return _kind_rule(root, node['values'], sources), {}
    if kind == 'source':
        matches = set()
        if 'email' in node['values'] and 'email' in sources:
            matches.update(('email', value) for value in _all_email_ids(root))
        if 'facebook' in node['values'] and 'facebook' in sources:
            matches.update(('catalog', value) for value in _all_catalog_ids(root))
        return matches, {}
    if kind == 'date':
        return _date_rule(root, node['after'], node['before'], sources), {}
    if kind == 'tag':
        return _tag_rule(root, node['values'], node['mode']), {}
    raise ValueError('unknown rule kind: ' + repr(kind))


def _chunks(values, size=400):
    values = list(values)
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _email_items(root, keys):
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file() or not keys:
        return {}
    conn = _connect(path)
    items = {}
    try:
        for chunk in _chunks(keys):
            placeholders = ','.join('?' for _ in chunk)
            rows = conn.execute(
                'SELECT hash,subject,sender,date,substr(body,1,200) FROM messages '
                f'WHERE hash IN ({placeholders})', chunk).fetchall()
            for digest, subject, sender, date, body in rows:
                items[('email', digest)] = {
                    'source': 'email', 'id': digest, 'kind': 'message',
                    'title': subject or '', 'actor': sender or '',
                    'date': date or '', 'snippet': (body or '')[:200]}
    finally:
        conn.close()
    return items


def _catalog_items(root, keys):
    path = Path(root) / 'catalog.sqlite3'
    if not path.is_file() or not keys:
        return {}
    conn = _connect(path)
    items = {}
    try:
        for chunk in _chunks(keys):
            placeholders = ','.join('?' for _ in chunk)
            rows = conn.execute(
                'SELECT record_id,source_key,record_kind,actor,occurred_at,'
                'substr(body,1,200) FROM records '
                f"WHERE source_type='facebook' AND record_id IN ({placeholders})", chunk)
            for record_id, source_key, kind, actor, occurred, body in rows:
                items[('catalog', record_id)] = {
                    'source': 'facebook', 'id': record_id, 'kind': kind,
                    'title': source_key or '', 'actor': actor or '',
                    'date': occurred or '', 'snippet': (body or '')[:200]}
    finally:
        conn.close()
    return items


def search_advanced(root, tree, limit=100, offset=0, sources=('email', 'facebook')):
    """Evaluate a nested boolean query tree and return one exact page."""
    nodes = normalize_query(tree)
    limit = max(1, min(int(limit), 5000))
    offset = max(0, int(offset))
    if isinstance(sources, str):
        sources = [part.strip() for part in sources.split(',') if part.strip()]
    sources = tuple(dict.fromkeys(sources))
    if not sources or any(source not in ('email', 'facebook') for source in sources):
        raise ValueError('sources must contain email and/or facebook')
    universe = _universe(root, sources) if _has_not(nodes) else set()
    matched, scores = _evaluate(nodes, root, sources, universe)
    keys = sorted(matched)
    metadata = _email_items(root, [key[1] for key in keys if key[0] == 'email'])
    metadata.update(_catalog_items(
        root, [key[1] for key in keys if key[0] == 'catalog']))
    items = [item for item in (metadata.get(key) for key in keys) if item is not None]

    def order(item):
        key = ('email' if item['source'] == 'email' else 'catalog', item['id'])
        return (-scores.get(key, 0.0), -(_epoch(item['date']) or 0.0),
                item['source'], item['id'])

    items.sort(key=order)
    page = items[offset:offset + limit]
    return {
        'items': page, 'total': len(items), 'offset': offset, 'limit': limit,
        'has_more': offset + len(page) < len(items), 'mode': 'boolean',
        'definitions': [
            'Groups are evaluated as sets over the selected sources: AND requires every '
            'child, OR requires any child, NOT excludes its single child.',
            'Text rules use FTS5 syntax and must be accepted by every selected index.',
            'Date rules use a half-open range [after, before) on normalized dates; '
            'undated records never match a date rule.',
            'Tag rules apply to email only because tags live in the research overlay.',
            'Results rank by summed text-rule relevance, then newest declared date; '
            'ties fall back to source and record id.',
            'Titles, actors, dates and snippets come from stored records; snippets are '
            'truncated stored text, never summaries.',
        ],
    }
