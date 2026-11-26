# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Source-independent catalog database with versioned, additive migrations."""
import sqlite3
from pathlib import Path

VERSION = 2

MIGRATIONS = {
    1: (
        "CREATE TABLE IF NOT EXISTS source_files("
        "file_hash TEXT PRIMARY KEY,"
        "source_type TEXT NOT NULL,"
        "source_key TEXT NOT NULL,"
        "path TEXT NOT NULL,"
        "size INTEGER NOT NULL,"
        "imported_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS records("
        "record_id TEXT PRIMARY KEY,"
        "source_type TEXT NOT NULL,"
        "source_key TEXT NOT NULL,"
        "record_kind TEXT NOT NULL,"
        "actor TEXT,"
        "occurred_at TEXT,"
        "occurred_precision TEXT,"
        "body TEXT,"
        "original_json TEXT,"
        "file_hash TEXT NOT NULL REFERENCES source_files(file_hash),"
        "created_at TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS records_by_kind ON records(source_type, record_kind)",
        "CREATE INDEX IF NOT EXISTS records_by_time ON records(occurred_at)",
    ),
    2: (
        "CREATE VIRTUAL TABLE IF NOT EXISTS record_search USING fts5(body, actor)",
        "CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN "
        "INSERT INTO record_search(rowid, body, actor) VALUES (new.rowid, new.body, new.actor); END",
        "CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN "
        "INSERT INTO record_search(record_search, rowid, body, actor) VALUES('delete', old.rowid, old.body, old.actor); END",
        "CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN "
        "INSERT INTO record_search(record_search, rowid, body, actor) VALUES('delete', old.rowid, old.body, old.actor); "
        "INSERT INTO record_search(rowid, body, actor) VALUES (new.rowid, new.body, new.actor); END",
        "INSERT INTO record_search(rowid, body, actor) SELECT rowid, body, actor FROM records",
    ),
}

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
        current = self.db.execute('PRAGMA user_version').fetchone()[0]
        for version in range(current + 1, VERSION + 1):
            with self.db:
                for statement in MIGRATIONS[version]:
                    self.db.execute(statement)
                self.db.execute(f'PRAGMA user_version={version}')

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
