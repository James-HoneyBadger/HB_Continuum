# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Source-independent catalog database with versioned, additive migrations."""
import json, sqlite3
from pathlib import Path

from .migrations import MIGRATIONS as _MIGRATIONS, apply as migrate, target_version

VERSION = target_version('catalog')
MIGRATIONS = _MIGRATIONS['catalog']

class Catalog:
    """Source-independent record catalog alongside the email archive.

    The catalog is additive and lives in its own catalog.sqlite3 so it can
    represent non-email sources without destabilizing archive.sqlite3.
    """
    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'catalog.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self._migrate()

    def _migrate(self):
        migrate(self.db, 'catalog')

    def close(self):
        self.db.close()

    def has_file(self, file_hash):
        return self.db.execute('SELECT 1 FROM source_files WHERE file_hash=?', (file_hash,)).fetchone() is not None

    def add_file(self, file_hash, source_type, source_key, path, size, imported_at):
        cur = self.db.execute('INSERT OR IGNORE INTO source_files VALUES(?,?,?,?,?,?)',
                              (file_hash, source_type, source_key, path, size, imported_at))
        return cur.rowcount == 1

    def has_record(self, record_id):
        return self.db.execute('SELECT 1 FROM records WHERE record_id=?', (record_id,)).fetchone() is not None

    def add_record(self, record_id, source_type, source_key, record_kind, actor,
                   occurred_at, precision, body, original_json, file_hash, created_at,
                   updated_at=None, revision_kind=None, revision_key=None,
                   revision_index=None, attachments_json='[]'):
        cur = self.db.execute(
            'INSERT OR IGNORE INTO records(record_id,source_type,source_key,record_kind,'
            'actor,occurred_at,occurred_precision,body,original_json,file_hash,created_at,'
            'updated_at,revision_kind,revision_key,revision_index,attachments_json) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (record_id, source_type, source_key, record_kind, actor, occurred_at,
             precision, body, original_json, file_hash, created_at, updated_at,
             revision_kind, revision_key, revision_index, attachments_json))
        return cur.rowcount == 1

    def record(self, record_id):
        """Full stored record with parsed attachment metadata, or None."""
        row = self.db.execute(
            'SELECT record_id,source_type,source_key,record_kind,actor,occurred_at,'
            'occurred_precision,body,original_json,file_hash,created_at,updated_at,'
            'revision_kind,revision_key,revision_index,attachments_json '
            'FROM records WHERE record_id=?', (record_id,)).fetchone()
        if row is None:
            return None
        keys = ('record_id', 'source_type', 'source_key', 'record_kind', 'actor',
                'occurred_at', 'occurred_precision', 'body', 'original_json',
                'file_hash', 'created_at', 'updated_at', 'revision_kind',
                'revision_key', 'revision_index', 'attachments_json')
        result = dict(zip(keys, row))
        try:
            attachments = json.loads(result.pop('attachments_json') or '[]')
        except (TypeError, ValueError):
            attachments = []
        result['attachments'] = attachments if isinstance(attachments, list) else []
        return result

    def list_records(self, source_type='facebook', record_kind=None, actor=None, limit=100):
        limit = max(1, min(int(limit), 5000))
        sql = 'SELECT record_id, source_key, record_kind, actor, occurred_at, body FROM records WHERE source_type=?'
        params = [source_type]
        if record_kind:
            sql += ' AND record_kind=?'
            params.append(record_kind)
        if actor:
            sql += ' AND actor=?'
            params.append(actor)
        sql += ' ORDER BY occurred_at DESC LIMIT ?'
        params.append(limit)
        return self.db.execute(sql, params).fetchall()

    def search_records(self, query, source_type='facebook', limit=100):
        limit = max(1, min(int(limit), 5000))
        sql = ('SELECT r.record_id, r.source_key, r.record_kind, r.actor, r.occurred_at, r.body '
               'FROM records r WHERE r.source_type=? AND r.rowid IN ('
               'SELECT rowid FROM record_search WHERE record_search MATCH ?) '
               'ORDER BY r.occurred_at DESC LIMIT ?')
        try:
            return self.db.execute(sql, (source_type, query, limit)).fetchall()
        except sqlite3.OperationalError:
            return []

    @staticmethod
    def _iso(value):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(value, timezone.utc).isoformat()

    def _ranked_filters(self, query, source_type, actor, kinds, after, before):
        clauses = ['r.source_type=?', 'record_search MATCH ?']
        params = [source_type, query]
        if actor:
            values = list(dict.fromkeys(actor))
            clauses.append('r.actor IN (' + ','.join('?' for _ in values) + ')')
            params.extend(values)
        if kinds:
            values = list(dict.fromkeys(kinds))
            clauses.append('r.record_kind IN (' + ','.join('?' for _ in values) + ')')
            params.extend(values)
        if after is not None:
            clauses.append('r.occurred_at >= ?')
            params.append(self._iso(after))
        if before is not None:
            clauses.append('r.occurred_at < ?')
            params.append(self._iso(before))
        return ' AND '.join(clauses), params

    def search_ranked(self, query, source_type='facebook', limit=100,
                      actor=None, kinds=None, after=None, before=None):
        """Matches ranked by the FTS5 bm25 score (best first)."""
        limit = max(1, min(int(limit), 5000))
        where, params = self._ranked_filters(query, source_type, actor, kinds, after, before)
        sql = ('SELECT r.record_id, r.source_key, r.record_kind, r.actor, r.occurred_at, r.body '
               'FROM records r JOIN record_search ON record_search.rowid = r.rowid '
               'WHERE ' + where + ' ORDER BY bm25(record_search) LIMIT ?')
        try:
            return self.db.execute(sql, (*params, limit)).fetchall()
        except sqlite3.OperationalError:
            return []

    def count_ranked(self, query, source_type='facebook',
                     actor=None, kinds=None, after=None, before=None):
        """Exact match count, or None when SQLite rejects the FTS expression."""
        where, params = self._ranked_filters(query, source_type, actor, kinds, after, before)
        sql = ('SELECT count(*) FROM records r '
               'JOIN record_search ON record_search.rowid = r.rowid WHERE ' + where)
        try:
            return self.db.execute(sql, params).fetchone()[0]
        except sqlite3.OperationalError:
            return None

    def stats(self):
        return {'files': self.db.execute('SELECT count(*) FROM source_files').fetchone()[0],
                'records': self.db.execute('SELECT count(*) FROM records').fetchone()[0]}
