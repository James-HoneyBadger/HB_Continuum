# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Source-independent catalog database with versioned, additive migrations."""
import json, sqlite3
from pathlib import Path

from .db import connect as db_connect
from .migrations import (MIGRATIONS as _MIGRATIONS, apply as migrate,
                         attachment_search_text, target_version)

VERSION = target_version('catalog')
MIGRATIONS = _MIGRATIONS['catalog']

def catalog_health(root):
    """Read-only consistency report for catalog.sqlite3.

    Never migrates or writes, so it is safe against an older catalog or one
    being imported concurrently. A missing or pre-schema catalog is reported
    as unavailable rather than treated as an error; an older schema is
    reported as not current and is never migrated here.
    """
    path = Path(root).expanduser()
    database = path / 'catalog.sqlite3'
    if not database.is_file():
        return {'available': False}
    try:
        conn = db_connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
    except sqlite3.Error:
        return {'available': False}
    try:
        conn.execute('PRAGMA query_only=ON')
        tables = {name for name, in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'records', 'record_search'} <= tables:
            return {'available': False}
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        checks = conn.execute('PRAGMA quick_check').fetchall()
        foreign = conn.execute('PRAGMA foreign_key_check').fetchall()
        records = conn.execute('SELECT count(*) FROM records').fetchone()[0]
        files = conn.execute('SELECT count(*) FROM source_files').fetchone()[0]
        indexed = conn.execute('SELECT count(*) FROM record_search').fetchone()[0]
        distinct = conn.execute('SELECT count(DISTINCT rowid) FROM record_search').fetchone()[0]
        missing = conn.execute(
            'SELECT count(*) FROM records r '
            'WHERE r.rowid NOT IN (SELECT rowid FROM record_search)').fetchone()[0]
        extra = conn.execute(
            'SELECT count(*) FROM record_search s '
            'WHERE s.rowid NOT IN (SELECT rowid FROM records)').fetchone()[0]
        dangling = conn.execute(
            'SELECT count(*) FROM records r '
            'WHERE r.file_hash NOT IN (SELECT file_hash FROM source_files)').fetchone()[0]
        try:
            invalid = conn.execute(
                'SELECT count(*) FROM records WHERE json_valid(attachments_json)=0'
            ).fetchone()[0]
        except sqlite3.OperationalError:
            invalid = None
        try:
            stale = conn.execute(
                'SELECT count(*) FROM records r '
                'JOIN record_search s ON s.rowid = r.rowid '
                "WHERE coalesce(r.body,'') != coalesce(s.body,'') "
                "OR coalesce(r.actor,'') != coalesce(s.actor,'') "
                "OR coalesce(r.attachments_text,'') != coalesce(s.attachments_text,'')"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            stale = None
        by_source = []
        types = [row[0] for row in conn.execute(
            'SELECT source_type FROM source_files UNION '
            'SELECT source_type FROM records ORDER BY 1')]
        for source_type in types:
            by_source.append({
                'source_type': source_type,
                'files': conn.execute(
                    'SELECT count(*) FROM source_files WHERE source_type=?',
                    (source_type,)).fetchone()[0],
                'records': conn.execute(
                    'SELECT count(*) FROM records WHERE source_type=?',
                    (source_type,)).fetchone()[0]})
    except sqlite3.Error:
        return {'available': False}
    finally:
        conn.close()
    duplicate_rows = indexed - distinct
    current = version >= VERSION
    consistent = (current and checks == [('ok',)] and not foreign and not missing
                  and not extra and not duplicate_rows and not stale and not dangling
                  and not invalid)
    return {'available': True, 'schema_version': version, 'schema_current': current,
            'sqlite_ok': checks == [('ok',)],
            'foreign_key_errors': len(foreign), 'records': records,
            'source_files': files, 'index_rows': indexed,
            'index_missing_rows': missing, 'index_extra_rows': extra,
            'index_duplicate_rows': duplicate_rows, 'index_stale_rows': stale,
            'dangling_file_references': dangling, 'invalid_attachments': invalid,
            'sources': by_source, 'consistent': consistent}

class Catalog:
    """Source-independent record catalog alongside the email archive.

    The catalog is additive and lives in its own catalog.sqlite3 so it can
    represent non-email sources without destabilizing archive.sqlite3.
    """
    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = db_connect(self.root / 'catalog.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self._migrate()

    def _migrate(self):
        migrate(self.db, 'catalog')

    def close(self):
        self.db.close()

    def reindex(self):
        """Rebuild the record full-text index from the stored records.

        The triggers keep record_search in step during normal writes, so this
        is a repair path for a drifted, truncated or partly rebuilt index.
        """
        with self.db:
            self.db.execute('DELETE FROM record_search')
            self.db.execute(
                'INSERT INTO record_search(rowid, body, actor, attachments_text) '
                'SELECT rowid, body, actor, attachments_text FROM records')
        return self.db.execute('SELECT count(*) FROM record_search').fetchone()[0]

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
                   revision_index=None, attachments_json='[]', attachments_text=None):
        """Insert one record, ignoring duplicates.

        Attachment metadata is searchable by contract: when the caller does not
        supply pre-flattened `attachments_text`, it is derived from
        `attachments_json` so a new source cannot silently hide it from search.
        """
        if attachments_text is None:
            attachments_text = attachment_search_text(attachments_json)
        cur = self.db.execute(
            'INSERT OR IGNORE INTO records(record_id,source_type,source_key,record_kind,'
            'actor,occurred_at,occurred_precision,body,original_json,file_hash,created_at,'
            'updated_at,revision_kind,revision_key,revision_index,attachments_json,'
            'attachments_text) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (record_id, source_type, source_key, record_kind, actor, occurred_at,
             precision, body, original_json, file_hash, created_at, updated_at,
             revision_kind, revision_key, revision_index, attachments_json,
             attachments_text))
        return cur.rowcount == 1

    def record(self, record_id):
        """Full stored record with parsed attachment metadata, or None."""
        row = self.db.execute(
            'SELECT record_id,source_type,source_key,record_kind,actor,occurred_at,'
            'occurred_precision,body,original_json,file_hash,created_at,updated_at,'
            'revision_kind,revision_key,revision_index,attachments_json,attachments_text '
            'FROM records WHERE record_id=?', (record_id,)).fetchone()
        if row is None:
            return None
        keys = ('record_id', 'source_type', 'source_key', 'record_kind', 'actor',
                'occurred_at', 'occurred_precision', 'body', 'original_json',
                'file_hash', 'created_at', 'updated_at', 'revision_kind',
                'revision_key', 'revision_index', 'attachments_json',
                'attachments_text')
        result = dict(zip(keys, row))
        try:
            attachments = json.loads(result.pop('attachments_json') or '[]')
        except (TypeError, ValueError):
            attachments = []
        result['attachments'] = attachments if isinstance(attachments, list) else []
        return result

    def record_revisions(self, record_id, limit=100):
        """Other stored versions sharing this record's revision key."""
        row = self.db.execute(
            'SELECT revision_key FROM records WHERE record_id=?', (record_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown record')
        if not row[0]:
            return []
        limit = max(1, min(int(limit), 500))
        rows = self.db.execute(
            'SELECT record_id,revision_index,revision_kind,occurred_at,updated_at,'
            'actor,substr(body,1,200) FROM records WHERE revision_key=? '
            'ORDER BY revision_index IS NULL, revision_index, '
            "COALESCE(updated_at,occurred_at,'') LIMIT ?", (row[0], limit)).fetchall()
        keys = ('record_id', 'revision_index', 'revision_kind', 'occurred_at',
                'updated_at', 'actor', 'body')
        latest_id = rows[-1][0] if rows else None
        result = []
        for values in rows:
            item = dict(zip(keys, values))
            item['current'] = item['record_id'] == latest_id
            result.append(item)
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
        sql = ('SELECT r.record_id, r.source_key, r.record_kind, r.actor, r.occurred_at, '
               "r.body, snippet(record_search, -1, '', '', '...', 32) "
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
