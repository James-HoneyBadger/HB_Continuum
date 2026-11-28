# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Create and unlock a new encrypted HB Continuum archive.

Only the database files are encrypted in this milestone. The KDF descriptor
contains public salt/parameters, never the password or derived key. Keys are
held only in process memory and are overwritten on an explicit lock.
"""
import base64
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import db

DESCRIPTOR_NAME = '.hb-encryption.json'
DATABASES = ('archive.sqlite3', 'research.sqlite3', 'catalog.sqlite3')
MIN_PASSWORD = 12
MAX_PASSWORD = 1024
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
SALT_BYTES = 16


class EncryptionError(ValueError):
    """Encrypted archive creation or unlocking failed."""


def descriptor_path(root):
    return Path(root).expanduser() / DESCRIPTOR_NAME


def is_encrypted_archive(root):
    return descriptor_path(root).is_file()


def _validate_descriptor(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise EncryptionError('unsupported encryption descriptor')
    if value.get('kdf') != 'scrypt' or value.get('cipher') != 'sqlcipher':
        raise EncryptionError('unsupported encryption descriptor')
    try:
        salt = base64.b64decode(value['salt'], validate=True)
        n = value['n']
        r = value['r']
        p = value['p']
        dklen = value['dklen']
    except (KeyError, TypeError, ValueError):
        raise EncryptionError('invalid encryption descriptor') from None
    if not 8 <= len(salt) <= 64:
        raise EncryptionError('invalid encryption salt')
    if (not isinstance(n, int) or isinstance(n, bool) or n < 2 ** 14
            or n > 2 ** 20 or n & (n - 1)):
        raise EncryptionError('invalid scrypt cost')
    if (not isinstance(r, int) or isinstance(r, bool) or not 1 <= r <= 16
            or not isinstance(p, int) or isinstance(p, bool) or not 1 <= p <= 4):
        raise EncryptionError('invalid scrypt parameters')
    if dklen != db.KEY_BYTES:
        raise EncryptionError('invalid derived key length')
    return {'version': 1, 'kdf': 'scrypt', 'cipher': 'sqlcipher',
            'salt': salt, 'n': n, 'r': r, 'p': p, 'dklen': dklen}


def read_descriptor(root):
    path = descriptor_path(root)
    try:
        return _validate_descriptor(json.loads(path.read_text(encoding='utf-8')))
    except FileNotFoundError:
        raise EncryptionError('archive is not encrypted') from None
    except (OSError, json.JSONDecodeError):
        raise EncryptionError('invalid encryption descriptor') from None


def _derive_key(password, descriptor):
    if not isinstance(password, str):
        raise EncryptionError('password must be text')
    if not password or len(password) > MAX_PASSWORD:
        raise EncryptionError('password is empty or too long')
    return hashlib.scrypt(
        password.encode('utf-8'), salt=descriptor['salt'],
        n=descriptor['n'], r=descriptor['r'], p=descriptor['p'],
        dklen=descriptor['dklen'], maxmem=SCRYPT_MAXMEM)


def _write_descriptor(staging, descriptor):
    payload = {
        'version': 1, 'kdf': 'scrypt', 'cipher': 'sqlcipher',
        'salt': base64.b64encode(descriptor['salt']).decode('ascii'),
        'n': descriptor['n'], 'r': descriptor['r'], 'p': descriptor['p'],
        'dklen': descriptor['dklen'],
    }
    path = descriptor_path(staging)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _close_archive(archive, catalog, research):
    for close in (getattr(research, 'close', None),
                  getattr(catalog, 'close', None),
                  getattr(getattr(archive, 'db', None), 'close', None)):
        if close is not None:
            try:
                close()
            except Exception:
                pass


def create(root, password, *, initialize=True):
    """Create three empty encrypted databases in a new archive directory.

    The destination must not exist or must be an empty directory. Creation is
    staged under the parent and renamed into place only after all databases and
    the descriptor are complete. No plaintext database is created.
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise EncryptionError(
            f'password must be at least {MIN_PASSWORD} characters')
    if not db.encryption_available():
        raise db.EncryptionUnavailable(
            'encrypted archive creation requires the optional sqlcipher3 package')
    if len(password) > MAX_PASSWORD:
        raise EncryptionError('password is too long')
    root = Path(root).expanduser().resolve()
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise EncryptionError('destination already exists and is not empty')
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.hb-encryption-', dir=root.parent))
    os.chmod(staging, 0o700)
    salt = os.urandom(SALT_BYTES)
    descriptor = {'salt': salt, 'n': SCRYPT_N, 'r': SCRYPT_R,
                  'p': SCRYPT_P, 'dklen': db.KEY_BYTES}
    key = _derive_key(password, descriptor)
    archive = catalog = research = None
    try:
        db.bind_session_key(staging, key)
        if initialize:
            from .catalog import Catalog
            from .dispatch import Archive
            from .research import Research
            archive = Archive(staging)
            catalog = Catalog(staging)
            research = Research(archive)
            _close_archive(archive, catalog, research)
        else:
            for name in DATABASES:
                conn = db.connect(staging / name, key=key)
                conn.close()
        _write_descriptor(staging, descriptor)
        db.clear_session_key(staging)
        if root.exists():
            root.rmdir()
        os.replace(staging, root)
    except BaseException:
        _close_archive(archive, catalog, research)
        db.clear_session_key(staging)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    db.bind_session_key(root, key)
    return status(root)


def unlock(root, password):
    """Derive the key and verify every existing database before binding it."""
    root = Path(root).expanduser().resolve()
    descriptor = read_descriptor(root)
    key = _derive_key(password, descriptor)
    try:
        for name in DATABASES:
            path = root / name
            if not path.is_file():
                continue
            conn = db.connect(path, key=key, readonly=True)
            try:
                conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
            finally:
                conn.close()
    except db.EncryptionUnavailable:
        raise
    except Exception:
        raise EncryptionError(
            'incorrect password or unreadable encrypted archive') from None
    db.bind_session_key(root, key)
    return status(root)


def lock(root):
    db.clear_session_key(root)
    return status(root)


def status(root):
    root = Path(root).expanduser().resolve()
    encrypted = is_encrypted_archive(root)
    databases = {}
    for name in DATABASES:
        path = root / name
        if path.is_file():
            databases[name] = {
                'encrypted': db.is_encrypted_file(path),
                'bytes': path.stat().st_size,
            }
    return {'encrypted': encrypted,
            'unlocked': db.session_unlocked(root),
            'available': db.encryption_available(),
            'databases': databases}
