# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Versioned, transactional schema migrations for the local databases.

Every statement is idempotent (`IF NOT EXISTS`), so version 1 is both the
baseline for a brand-new database and the upgrade path for an existing one.
Versions are tracked with `PRAGMA user_version`, which SQLite stores in the
database header and updates inside the same transaction as the DDL.

Opening a database written by a newer build raises instead of proceeding, so
an older binary cannot silently damage a newer archive.
"""
import sqlite3
from pathlib import Path

class MigrationError(RuntimeError):
    pass

DATABASES = (('archive', 'archive.sqlite3'),
             ('research', 'research.sqlite3'),
             ('catalog', 'catalog.sqlite3'))

ARCHIVE_V1 = (
    'CREATE TABLE IF NOT EXISTS messages('
    'hash TEXT PRIMARY KEY, subject TEXT, sender TEXT, date TEXT, '
    'message_id TEXT, reply_to TEXT, body TEXT)',
    'CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5('
    'hash UNINDEXED, subject, sender, body)',
    'CREATE INDEX IF NOT EXISTS messages_message_id ON messages(message_id)',
    'CREATE INDEX IF NOT EXISTS messages_reply_to ON messages(reply_to)',
    'CREATE TABLE IF NOT EXISTS origins('
    'account TEXT, folder TEXT, validity TEXT, uid TEXT, '
    'hash TEXT NOT NULL REFERENCES messages(hash), '
    'PRIMARY KEY(account,folder,validity,uid))',
)

ARCHIVE_V2 = (
    'CREATE TABLE IF NOT EXISTS attachment_index('
    'hash TEXT NOT NULL REFERENCES messages(hash), part INTEGER, '
    'filename TEXT, mime TEXT, content TEXT, PRIMARY KEY(hash,part))',
    'CREATE TABLE IF NOT EXISTS extraction_versions('
    'hash TEXT PRIMARY KEY REFERENCES messages(hash), version INTEGER NOT NULL)',
)

RESEARCH_V1 = (
    'CREATE TABLE IF NOT EXISTS workspaces('
    'name TEXT PRIMARY KEY, description TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS searches('
    'workspace TEXT REFERENCES workspaces(name) ON DELETE CASCADE, '
    'name TEXT, query TEXT NOT NULL, tag TEXT NOT NULL, limit_n INTEGER NOT NULL, '
    'PRIMARY KEY(workspace,name))',
    'CREATE TABLE IF NOT EXISTS tags('
    'hash TEXT, tag TEXT, source TEXT, PRIMARY KEY(hash,tag,source))',
    'CREATE INDEX IF NOT EXISTS tags_by_name ON tags(tag,hash)',
    'CREATE TABLE IF NOT EXISTS rules('
    'name TEXT PRIMARY KEY, field TEXT, operator TEXT, value TEXT, tag TEXT, enabled INTEGER)',
    'CREATE TABLE IF NOT EXISTS fields(name TEXT PRIMARY KEY, type TEXT, choices TEXT)',
    'CREATE TABLE IF NOT EXISTS metadata('
    'hash TEXT, field TEXT REFERENCES fields(name) ON DELETE CASCADE, value TEXT, '
    'PRIMARY KEY(hash,field))',
    'CREATE TABLE IF NOT EXISTS reports('
    'name TEXT PRIMARY KEY, workspace TEXT, search TEXT, columns TEXT, group_by TEXT)',
    'CREATE TABLE IF NOT EXISTS summaries('
    'message_hash TEXT NOT NULL, '
    "summary_type TEXT NOT NULL CHECK (summary_type IN ('message','thread')), "
    'model_name TEXT NOT NULL, prompt_version TEXT NOT NULL, '
    'summary_text TEXT NOT NULL, created_at TEXT NOT NULL, '
    'input_digest TEXT, thread_members TEXT, '
    'PRIMARY KEY (message_hash, summary_type, model_name, prompt_version))',
    'CREATE INDEX IF NOT EXISTS summaries_lookup ON summaries('
    'summary_type, model_name, prompt_version, message_hash)',
)

CATALOG_V1 = (
    'CREATE TABLE IF NOT EXISTS source_files('
    'file_hash TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_key TEXT NOT NULL, '
    'path TEXT NOT NULL, size INTEGER NOT NULL, imported_at TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS records('
    'record_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_key TEXT NOT NULL, '
    'record_kind TEXT NOT NULL, actor TEXT, occurred_at TEXT, occurred_precision TEXT, '
    'body TEXT, original_json TEXT, '
    'file_hash TEXT NOT NULL REFERENCES source_files(file_hash), created_at TEXT NOT NULL)',
    'CREATE INDEX IF NOT EXISTS records_by_kind ON records(source_type, record_kind)',
    'CREATE INDEX IF NOT EXISTS records_by_time ON records(occurred_at)',
)

CATALOG_V2 = (
    'CREATE VIRTUAL TABLE IF NOT EXISTS record_search USING fts5(body, actor)',
    'CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN '
    'INSERT INTO record_search(rowid, body, actor) VALUES (new.rowid, new.body, new.actor); END',
    'CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN '
    "INSERT INTO record_search(record_search, rowid, body, actor) VALUES('delete', old.rowid, old.body, old.actor); END",
    'CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN '
    "INSERT INTO record_search(record_search, rowid, body, actor) VALUES('delete', old.rowid, old.body, old.actor); "
    'INSERT INTO record_search(rowid, body, actor) VALUES (new.rowid, new.body, new.actor); END',
    'INSERT INTO record_search(rowid, body, actor) SELECT rowid, body, actor FROM records',
)

MIGRATIONS = {
    'archive': {1: ARCHIVE_V1, 2: ARCHIVE_V2},
    'research': {1: RESEARCH_V1},
    'catalog': {1: CATALOG_V1, 2: CATALOG_V2},
}

def target_version(name):
    try:
        return max(MIGRATIONS[name])
    except KeyError:
        raise MigrationError(f'Unknown database {name!r}') from None

def current_version(db):
    return db.execute('PRAGMA user_version').fetchone()[0]

def pending(name, version):
    return [v for v in sorted(MIGRATIONS[name]) if v > version]

def has_schema(db):
    """True when the database already contains user tables (i.e. not brand new)."""
    return db.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0] > 0

def snapshot(db, path):
    """Copy the database through SQLite's backup API before migrating."""
    destination = sqlite3.connect(str(path))
    try:
        db.backup(destination)
    finally:
        destination.close()
    return str(path)

def apply(db, name, snapshot_path=None):
    """Bring `db` up to the newest known version for `name`.

    Returns a dict describing the transition. Pending DDL runs one version per
    transaction together with its `user_version` bump, so an interrupted
    migration leaves the database at the previous version.
    """
    target = target_version(name)
    version = current_version(db)
    if version > target:
        raise MigrationError(
            f'The {name} database was written by a newer version '
            f'(schema {version}, this build supports {target}). '
            'Upgrade the application instead of opening it with an older build.')
    steps = pending(name, version)
    if not steps:
        return {'database': name, 'from': version, 'to': version, 'applied': []}
    if snapshot_path is not None and has_schema(db):
        snapshot(db, snapshot_path)
    for step in steps:
        with db:
            for statement in MIGRATIONS[name][step]:
                db.execute(statement)
            db.execute(f'PRAGMA user_version={step}')
    return {'database': name, 'from': version, 'to': target, 'applied': steps}

def report(root, dry_run=False, snapshot_=True):
    """Inspect (and unless dry_run, migrate) every database under `root`.

    Runs without constructing Archive or Research, so it reports and migrates
    the real on-disk versions instead of whatever those constructors leave.
    """
    root = Path(root)
    result = {}
    for name, filename in DATABASES:
        path = root / filename
        if not path.is_file():
            result[name] = {'present': False, 'target': target_version(name)}
            continue
        conn = sqlite3.connect(str(path), timeout=30)
        try:
            version = current_version(conn)
            if dry_run:
                result[name] = {'present': True, 'version': version,
                                'target': target_version(name),
                                'pending': pending(name, version)}
                continue
            backup = path.with_name(f'{path.stem}.v{version}.backup.sqlite3') if snapshot_ else None
            outcome = apply(conn, name, snapshot_path=backup)
            outcome['present'] = True
            outcome['snapshot'] = str(backup) if backup is not None and backup.exists() else None
            result[name] = outcome
        except MigrationError as exc:
            result[name] = {'present': True, 'error': str(exc)}
        finally:
            conn.close()
    return result
