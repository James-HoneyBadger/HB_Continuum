# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Central SQLite and SQLCipher connection service.

Existing archives remain plaintext and continue to use the standard-library
``sqlite3`` driver. Passing a 32-byte key selects the separately installed
``sqlcipher3`` driver and applies the key before any query. There is no
fallback from a requested encrypted connection to a plaintext one.
"""
import importlib
import sqlite3
from pathlib import Path

KEY_BYTES = 32


class EncryptionUnavailable(RuntimeError):
    """The sqlcipher3 binding is not installed in this environment."""


class InvalidDatabaseKey(ValueError):
    """A database key is not a supported raw 32-byte key."""


def encryption_available():
    try:
        importlib.import_module('sqlcipher3')
    except ImportError:
        return False
    return True


def _sqlcipher():
    try:
        return importlib.import_module('sqlcipher3')
    except ImportError as exc:
        raise EncryptionUnavailable(
            'Encrypted database access requires the optional sqlcipher3 package; '
            'no plaintext fallback was attempted') from exc


def _key_bytes(key):
    if isinstance(key, str):
        raise InvalidDatabaseKey(
            'database keys must be raw bytes, not passphrases or text')
    try:
        value = bytes(key)
    except (TypeError, ValueError):
        raise InvalidDatabaseKey('database key must be bytes-like') from None
    if len(value) != KEY_BYTES:
        raise InvalidDatabaseKey(
            f'database key must be exactly {KEY_BYTES} bytes')
    return value


def connect(path, *, key=None, timeout=30, uri=False, readonly=False):
    """Open a database, encrypted only when a raw key is supplied.

    ``readonly`` applies ``PRAGMA query_only`` after any key is installed, so
    callers cannot write through a read-only connection. A requested encrypted
    connection never falls back to plaintext if ``sqlcipher3`` is missing or
    the key is wrong; those errors propagate.
    """
    if key is None:
        conn = sqlite3.connect(str(path), timeout=timeout, uri=uri)
        if readonly:
            conn.execute('PRAGMA query_only=ON')
        return conn
    value = _key_bytes(key)
    driver = _sqlcipher()
    conn = driver.connect(str(path), timeout=timeout, uri=uri)
    try:
        # A raw key avoids SQL quoting of a user passphrase. The hex value is
        # safe to interpolate and never includes the key as text.
        conn.execute(f'PRAGMA key = "x\'{value.hex()}\'"')
        if readonly:
            conn.execute('PRAGMA query_only=ON')
        # Force key verification before handing the connection to a caller.
        conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
    except BaseException:
        conn.close()
        raise
    return conn


def is_encrypted_file(path):
    """Best-effort check for a SQLCipher file, for diagnostics and tests only."""
    path = Path(path)
    try:
        with path.open('rb') as handle:
            return handle.read(16) != b'SQLite format 3\x00'
    except OSError:
        return False
