# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Source-independent catalog database with versioned, additive migrations."""
import sqlite3
from pathlib import Path

from migrations import MIGRATIONS as _MIGRATIONS, apply as migrate, target_version

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
                   occurred_at, precision, body, original_json, file_hash, created_at):
        cur = self.db.execute(
            'INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (record_id, source_type, source_key, record_kind, actor, occurred_at,
             precision, body, original_json, file_hash, created_at))
        return cur.rowcount == 1

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

    def stats(self):
        return {'files': self.db.execute('SELECT count(*) FROM source_files').fetchone()[0],
                'records': self.db.execute('SELECT count(*) FROM records').fetchone()[0]}
