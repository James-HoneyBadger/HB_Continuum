# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Transactional, user-initiated plaintext-to-encrypted archive migration.

The original archive is never modified or deleted. Migration creates a
verified plaintext backup, builds an encrypted destination in a staging
directory, validates both the encrypted copy and a restored backup, and only
then publishes the destination.
"""
import hashlib
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from . import backup, db, encryption
from .migrations import DATABASES as MIGRATION_DATABASES
from .migrations import apply as apply_migrations
from .migrations import target_version
from .sync_lock import sync_lock

DATABASES = tuple(filename for _, filename in MIGRATION_DATABASES)
RESEARCH_TABLES = ('workspaces', 'searches', 'tags', 'metadata', 'fields',
                   'rules', 'collections', 'collection_items', 'journal_entries',
                   'journal_revisions', 'report_drafts', 'advanced_queries',
                   'research_conversations', 'research_turns')
SPACE_MARGIN = 64 * 1024 * 1024


class MigrationError(RuntimeError):
    pass


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _plain(path, readonly=True):
    if readonly:
        return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    return sqlite3.connect(str(path))


def _encrypted(path, key):
    return db.connect(path, key=key)


def _source_versions(source):
    versions = {}
    for name in DATABASES:
        path = source / name
        if not path.is_file():
            versions[name] = None
            continue
        if db.is_encrypted_file(path):
            raise MigrationError(f'{path} is already encrypted or unreadable')
        conn = _plain(path)
        try:
            check = conn.execute('PRAGMA quick_check').fetchall()
            if check != [('ok',)]:
                raise MigrationError(f'{path} failed SQLite quick_check')
            version = conn.execute('PRAGMA user_version').fetchone()[0]
        finally:
            conn.close()
        target = target_version(name.split('.')[0])
        if version > target:
            raise MigrationError(
                f'{path} schema {version} is newer than supported {target}')
        versions[name] = version
    if versions['archive.sqlite3'] is None:
        raise MigrationError('source archive has no archive.sqlite3')
    return versions


def _source_size(source):
    total = 0
    for path in source.rglob('*'):
        if path.is_symlink():
            raise MigrationError(f'source contains a symbolic link: {path}')
        if path.is_file():
            total += path.stat().st_size
    return total


def _check_space(source, backup_path, destination):
    needed = _source_size(source) + SPACE_MARGIN
    parents = {backup_path.parent.resolve(), destination.parent.resolve()}
    for parent in parents:
        parent.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(parent).free
        require = needed * 2 if len(parents) == 1 else needed
        if free < require:
            raise MigrationError(
                f'insufficient storage in {parent}: need about {require} bytes, '
                f'{free} available')


def _copy_runtime_files(source, staging):
    raw_source = source / 'raw'
    raw_target = staging / 'raw'
    raw_target.mkdir(mode=0o700, exist_ok=True)
    if raw_source.is_dir():
        for entry in sorted(raw_source.iterdir()):
            if entry.is_symlink():
                raise MigrationError(f'unsafe raw entry: {entry}')
            if not entry.is_file():
                raise MigrationError(f'unexpected raw entry: {entry}')
            shutil.copy2(entry, raw_target / entry.name)
    for name in backup.CONFIG:
        path = source / name
        if path.is_file():
            if path.is_symlink():
                raise MigrationError(f'unsafe configuration entry: {path}')
            shutil.copy2(path, staging / name)


def _export_database(source_db, destination_db, key):
    import sqlcipher3  # type: ignore[import-not-found]
    source = sqlcipher3.connect(source_db.resolve().as_uri() + '?mode=ro',
                                uri=True)
    try:
        source.execute(
            f'ATTACH DATABASE ? AS encrypted KEY "x\'{key.hex()}\'"',
            (str(destination_db),))
        source.execute("SELECT sqlcipher_export('encrypted')")
        source.execute('DETACH DATABASE encrypted')
        version = source.execute('PRAGMA user_version').fetchone()[0]
        application_id = source.execute('PRAGMA application_id').fetchone()[0]
    finally:
        source.close()
    destination = db.connect(destination_db, key=key)
    try:
        destination.execute(f'PRAGMA user_version={int(version)}')
        destination.execute(f'PRAGMA application_id={int(application_id)}')
        name = destination_db.name.split('.')[0]
        outcome = apply_migrations(destination, name)
    finally:
        destination.close()
    return outcome


def _tables(conn):
    return [name for name, in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _schema_names(conn):
    return {(kind, name) for kind, name in conn.execute(
        "SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}


def _table_counts(conn):
    counts = {}
    for name in _tables(conn):
        try:
            counts[name] = conn.execute(f'SELECT count(*) FROM {_quote(name)}').fetchone()[0]
        except sqlite3.Error as exc:
            raise MigrationError(f'cannot count {name}: {exc}') from None
    return counts


def _fts_checks(conn):
    names = [name for name, sql in conn.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='table' AND sql LIKE 'CREATE VIRTUAL TABLE%'")]
    for name in names:
        conn.execute(f'INSERT INTO {_quote(name)}({_quote(name)}) VALUES (\'integrity-check\')')
    return names


def _columns(conn, name):
    return [row[1] for row in conn.execute(f'PRAGMA table_info({_quote(name)})')]


def _digest_table(conn, name, columns):
    digest = hashlib.sha256()
    selected = ','.join(_quote(column) for column in columns)
    for row in conn.execute(
            f'SELECT {selected} FROM {_quote(name)} ORDER BY rowid'):
        digest.update(repr(row).encode('utf-8', 'backslashreplace'))
        digest.update(b'\n')
    return digest.hexdigest()


def _raw_hashes(root):
    result = {}
    raw = root / 'raw'
    if not raw.is_dir():
        return result
    for path in sorted(raw.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise MigrationError(f'unsafe raw entry in {root}: {path}')
        with path.open('rb') as handle:
            result[path.name] = hashlib.file_digest(handle, 'sha256').hexdigest()
    return result


def _validate_pair(source, destination, destination_key=None, raw_all=True):
    source_versions = _source_versions(source)
    details = {}
    source_raw = _raw_hashes(source)
    destination_raw = _raw_hashes(destination)
    if raw_all:
        if source_raw != destination_raw:
            raise MigrationError('raw file hashes differ between source and destination')
    else:
        referenced = {}
        conn = _plain(source / 'archive.sqlite3')
        try:
            for digest, in conn.execute('SELECT hash FROM messages'):
                name = digest + '.eml'
                if name in source_raw:
                    referenced[name] = source_raw[name]
        finally:
            conn.close()
        if any(destination_raw.get(name) != digest for name, digest in referenced.items()):
            raise MigrationError('restored raw files do not match source messages')
    for name in DATABASES:
        source_path = source / name
        if not source_path.is_file():
            continue
        destination_path = destination / name
        if not destination_path.is_file():
            raise MigrationError(f'destination is missing {name}')
        src = _plain(source_path)
        dst = (_encrypted(destination_path, destination_key)
               if destination_key is not None else _plain(destination_path, readonly=False))
        try:
            if src.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise MigrationError(f'source {name} failed quick_check')
            if dst.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise MigrationError(f'destination {name} failed quick_check')
            source_schema = _schema_names(src)
            destination_schema = _schema_names(dst)
            missing = source_schema - destination_schema
            if missing:
                raise MigrationError(f'destination {name} is missing schema objects: {sorted(missing)}')
            source_counts = _table_counts(src)
            destination_counts = _table_counts(dst)
            for table, count in source_counts.items():
                if destination_counts.get(table) != count:
                    raise MigrationError(
                        f'{name}.{table} row count differs: {count} vs '
                        f'{destination_counts.get(table)}')
            fts = _fts_checks(dst)
            versions = {'source': source_versions[name],
                        'destination': dst.execute('PRAGMA user_version').fetchone()[0]}
            if destination_key is not None:
                target = target_version(name.split('.')[0])
                if versions['destination'] != target:
                    raise MigrationError(f'{name} destination schema is {versions["destination"]}, expected {target}')
            details[name] = {'versions': versions, 'tables': len(source_counts),
                             'rows': sum(source_counts.values()), 'fts': fts}
            if name == 'research.sqlite3':
                for table in RESEARCH_TABLES:
                    if table not in source_counts or table not in destination_counts:
                        continue
                    columns = [column for column in _columns(src, table)
                               if column in _columns(dst, table)]
                    if _digest_table(src, table, columns) != _digest_table(dst, table, columns):
                        raise MigrationError(f'research table {table} differs')
            if name == 'archive.sqlite3':
                source_hashes = [row[0] for row in src.execute(
                    'SELECT hash FROM messages ORDER BY hash')]
                destination_hashes = [row[0] for row in dst.execute(
                    'SELECT hash FROM messages ORDER BY hash')]
                if source_hashes != destination_hashes:
                    raise MigrationError('message hash list differs')
        finally:
            src.close()
            dst.close()
    return details


def _publish(staging, destination):
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise MigrationError('destination already exists and is not empty')
        destination.rmdir()
    os.replace(staging, destination)


def migrate(source, destination, backup_path, password):
    """Migrate one plaintext archive to a new encrypted archive.

    The source is held under the exclusive archive lock throughout. The original
    directory is never modified or removed. All temporary encrypted data lives
    in a staging directory and is discarded on failure.
    """
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    backup_path = Path(backup_path).expanduser().resolve()
    if not source.is_dir():
        raise MigrationError('source archive directory does not exist')
    if encryption.is_encrypted_archive(source):
        raise MigrationError('source archive is already encrypted')
    if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise MigrationError('destination must be outside the source archive')
    if backup_path == source or backup_path.is_relative_to(source):
        raise MigrationError('backup must be outside the source archive')
    if backup_path == destination or backup_path.is_relative_to(destination) or destination.is_relative_to(backup_path):
        raise MigrationError('backup and destination must be separate')
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise MigrationError('destination already exists and is not empty')
    if backup_path.exists():
        raise MigrationError('backup destination already exists')
    if not db.encryption_available():
        raise MigrationError('encrypted migration requires the optional sqlcipher3 package')
    if not isinstance(password, str) or len(password) < encryption.MIN_PASSWORD:
        raise encryption.EncryptionError(
            f'password must be at least {encryption.MIN_PASSWORD} characters')
    staging = Path(tempfile.mkdtemp(prefix='.hb-migration-', dir=destination.parent))
    key = None
    try:
        with sync_lock(source):
            _check_space(source, backup_path, destination)
            source_versions = _source_versions(source)
            backup_result = backup.backup(source, backup_path, lock=False)
            backup.validate_snapshot(backup_path)
            encryption.create(staging, password, initialize=False)
            descriptor = encryption.read_descriptor(staging)
            key = encryption._derive_key(password, descriptor)
            _copy_runtime_files(source, staging)
            for name in DATABASES:
                if (source / name).is_file():
                    _export_database(source / name, staging / name, key)
            details = _validate_pair(source, staging, destination_key=key, raw_all=True)
            with tempfile.TemporaryDirectory(dir=destination.parent,
                                             prefix='.hb-restore-check-') as restore_tmp:
                restored = Path(restore_tmp) / 'restored'
                backup.restore(backup_path, restored)
                restored_details = _validate_pair(source, restored, raw_all=False)
            encryption.lock(staging)
            key = None
            _publish(staging, destination)
        return {
            'source': str(source),
            'destination': str(destination),
            'backup': str(backup_path),
            'backup_verified': True,
            'restoration_verified': True,
            'source_versions': source_versions,
            'destination_databases': details,
            'restored_databases': restored_details,
            'backup_result': backup_result,
            'warning': (
                'The original archive was not modified or deleted. The verified '
                'backup and any older backups, filesystem snapshots or copies may '
                'still contain plaintext data.'),
        }
    except (MigrationError, encryption.EncryptionError, db.EncryptionUnavailable):
        if key is not None:
            encryption.lock(staging)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception as exc:
        if key is not None:
            encryption.lock(staging)
        shutil.rmtree(staging, ignore_errors=True)
        raise MigrationError(
            f'migration failed: {type(exc).__name__}: {exc}') from None
    except BaseException:
        if key is not None:
            encryption.lock(staging)
        shutil.rmtree(staging, ignore_errors=True)
        raise
