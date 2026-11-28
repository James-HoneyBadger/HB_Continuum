# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Independent, verified snapshots of an archive directory.

A snapshot is a directory holding the databases, the configuration files and
every raw original, plus a manifest of SHA-256 hashes. Snapshots are built in
a staging directory, validated, and only then renamed into place, so a
partial or tampered copy is never mistaken for a usable backup.
"""
import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing, nullcontext
from pathlib import Path

from . import db as db_service
from .encryption import DESCRIPTOR_NAME, is_encrypted_archive
from .migrations import DATABASES as _DATABASES
from .sync_lock import sync_lock

# Derive the backup set from the migration registry so a new database cannot
# be silently omitted from preservation.
DATABASES = tuple(name for _, name in _DATABASES)
CONFIG = ('preferences.json', 'schedule.json', 'schedule-status.json',
          '.hb-encryption.json')
MANIFEST = 'backup-manifest.json'

def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def connect(path, key=None):
    """Open a database read-only through a file URI, so validation cannot write."""
    return db_service.connect(path.resolve().as_uri() + '?mode=ro', uri=True, key=key)

def copydb(source, target, key=None):
    with closing(connect(source, key=key)) as src, \
         closing(db_service.connect(target, key=key)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower() != 'delete':
            raise ValueError('Cannot normalize snapshot journal mode')
    # A source in WAL mode can leave an empty shared-memory sidecar behind even
    # after the journal mode is normalized; it is not part of the snapshot.
    for suffix in ('-wal', '-shm'):
        sidecar = target.with_name(target.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

def _entries(root):
    """Every entry below `root`, refusing symlinks and special files."""
    pending = [root]
    entries = []
    while pending:
        for child in pending.pop().iterdir():
            if child.is_symlink():
                raise ValueError('Unsafe snapshot entry')
            if child.is_dir():
                pending.append(child)
            elif not child.is_file():
                raise ValueError('Unsafe snapshot entry')
            entries.append(child)
    return entries

def _valid_raw_name(name):
    stem, _, suffix = name.rpartition('.')
    return (name.startswith('raw/') and suffix == 'eml' and len(stem) == 68
            and all(c in '0123456789abcdef' for c in stem[4:]))

def validate_snapshot(root, key=None):
    """Raise ValueError unless `root` is a complete, unaltered snapshot."""
    root = Path(root)
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError('Unsafe manifest')
    if not manifest_path.is_file():
        raise ValueError('Missing backup manifest')
    if is_encrypted_archive(root) and key is None:
        raise ValueError('Encrypted backup must be unlocked before validation')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Invalid backup manifest')
    expected = manifest['files']
    entries = _entries(root)
    if any(p.is_dir() and p.relative_to(root).as_posix() != 'raw' for p in entries):
        raise ValueError('Unexpected snapshot directory')
    actual = {p.relative_to(root).as_posix() for p in entries
              if p.is_file() and p != root / MANIFEST}
    allowed = set(DATABASES + CONFIG)
    if any(name not in allowed and not _valid_raw_name(name) for name in actual):
        raise ValueError('Unexpected snapshot file')
    if set(expected) != actual:
        raise ValueError('Backup file set mismatch')
    for name, recorded in expected.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or digest(path) != recorded:
            raise ValueError('Backup hash mismatch: ' + name)
    for name in DATABASES:
        if name not in expected:
            if name == 'archive.sqlite3':
                raise ValueError('Missing archive database')
            continue
        with closing(connect(root / name, key=key)) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite integrity failure')
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Foreign key failure')
            if name == 'archive.sqlite3':
                hashes = {h for h, in db.execute('SELECT hash FROM messages')}
                indexed = [h for h, in db.execute('SELECT hash FROM search')]
                if hashes != set(indexed) or len(set(indexed)) != len(indexed):
                    raise ValueError('Search index mismatch')
                for h in hashes:
                    if expected.get('raw/' + h + '.eml') != h:
                        raise ValueError('Original message missing or altered: ' + h)
            elif name == 'catalog.sqlite3':
                tables = {t for t, in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if {'records', 'record_search'} <= tables:
                    records = {rowid for rowid, in db.execute('SELECT rowid FROM records')}
                    indexed = [rowid for rowid, in db.execute('SELECT rowid FROM record_search')]
                    if records != set(indexed) or len(set(indexed)) != len(indexed):
                        raise ValueError('Catalog search index mismatch')
                    try:
                        stale = db.execute(
                            'SELECT count(*) FROM records r '
                            'JOIN record_search s ON s.rowid = r.rowid '
                            "WHERE coalesce(r.body,'') != coalesce(s.body,'') "
                            "OR coalesce(r.actor,'') != coalesce(s.actor,'') "
                            "OR coalesce(r.attachments_text,'') != coalesce(s.attachments_text,'')"
                        ).fetchone()[0]
                    except sqlite3.OperationalError:
                        stale = 0
                    if stale:
                        raise ValueError('Catalog search index content mismatch')
    return {'files': len(expected), 'verified': True}

def publish_stage(stage, dest):
    """Reserve the destination atomically; never replace an existing backup."""
    dest.mkdir(mode=0o700)
    try:
        for child in stage.iterdir():
            child.rename(dest / child.name)
    except BaseException:
        shutil.rmtree(dest)
        raise

def backup(root, destination, *, lock=True):
    root = Path(root).expanduser().resolve()
    dest = Path(destination).expanduser().resolve()
    encrypted = is_encrypted_archive(root)
    key = db_service.session_key(root) if encrypted else None
    if encrypted and key is None:
        raise ValueError('Encrypted archive must be unlocked before backup')
    if dest.is_relative_to(root) or root.is_relative_to(dest):
        raise ValueError('Backup must be outside archive')
    if dest.exists():
        raise FileExistsError(f'Destination already exists: {dest}')
    if not (root / 'archive.sqlite3').is_file():
        raise ValueError('No archive database to back up')
    if (root / 'raw').is_symlink():
        raise ValueError('Unsafe source raw directory')
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock_context = sync_lock(root) if lock else nullcontext()
    with lock_context, tempfile.TemporaryDirectory(dir=dest.parent, prefix='.hb-backup-') as tmp:
        stage = Path(tmp)
        (stage / 'raw').mkdir(mode=0o700)
        for name in DATABASES:
            if (root / name).is_file():
                if (root / name).is_symlink():
                    raise ValueError('Unsafe source database')
                copydb(root / name, stage / name, key=key)
        for name in CONFIG:
            if (root / name).is_file():
                if (root / name).is_symlink():
                    raise ValueError('Unsafe source configuration')
                shutil.copy2(root / name, stage / name)
                if name == DESCRIPTOR_NAME:
                    (stage / name).chmod(0o600)
        with closing(connect(stage / 'archive.sqlite3', key=key)) as db:
            for h, in db.execute('SELECT hash FROM messages'):
                if len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
                    raise ValueError('Invalid message hash')
                source = root / 'raw' / (h + '.eml')
                if source.is_symlink():
                    raise ValueError('Unsafe source message')
                shutil.copyfile(source, stage / 'raw' / (h + '.eml'))
        files = {p.relative_to(stage).as_posix(): digest(p) for p in stage.rglob('*') if p.is_file()}
        (stage / MANIFEST).write_text(json.dumps({'version': 1, 'files': files}, indent=2))
        result = validate_snapshot(stage, key=key)
        result['encrypted'] = encrypted
        if encrypted:
            result['warning'] = (
                'Database files in this backup are encrypted with the archive key. '
                'Raw EML files, configuration and reports are not encrypted.')
        else:
            result['warning'] = (
                'This backup contains plaintext databases and raw files.')
        publish_stage(stage, dest)
        return result

def restore(snapshot, destination, key=None):
    src = Path(snapshot).expanduser().resolve()
    dest = Path(destination).expanduser().resolve()
    encrypted = is_encrypted_archive(src)
    if encrypted and key is None:
        key = db_service.session_key(src)
    if encrypted and key is None:
        raise ValueError('Encrypted backup must be unlocked before restore')
    if dest.is_relative_to(src) or src.is_relative_to(dest):
        raise ValueError('Restore must use independent destination')
    if dest.exists():
        raise FileExistsError(f'Destination already exists: {dest}')
    validate_snapshot(src, key=key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix='.hb-restore-') as tmp:
        stage = Path(tmp)
        for child in src.iterdir():
            if child.is_dir():
                shutil.copytree(child, stage / child.name)
            else:
                shutil.copy2(child, stage / child.name)
                if child.name == DESCRIPTOR_NAME:
                    (stage / child.name).chmod(0o600)
        result = validate_snapshot(stage, key=key)
        # A restored copy must not resume background jobs on its own.
        path = stage / 'schedule.json'
        if path.exists():
            profiles = json.loads(path.read_text())
            for profile in profiles.values():
                profile['enabled'] = False
            path.write_text(json.dumps(profiles, indent=2))
        # Disabling scheduling changes the schedule file, so refresh the
        # manifest and validate the restored snapshot before publishing it.
        (stage / MANIFEST).unlink()
        files = {p.relative_to(stage).as_posix(): digest(p)
                 for p in stage.rglob('*') if p.is_file()}
        (stage / MANIFEST).write_text(json.dumps({'version': 1, 'files': files}, indent=2))
        result = validate_snapshot(stage, key=key)
        result['encrypted'] = encrypted
        if encrypted:
            result['warning'] = (
                'Database files in this backup are encrypted with the archive key. '
                'Raw EML files, configuration and reports are not encrypted.')
        else:
            result['warning'] = 'This restored archive contains plaintext databases and raw files.'
        publish_stage(stage, dest)
        return result
