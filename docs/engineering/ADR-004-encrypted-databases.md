# ADR-004: Encrypted SQLite feasibility foundation

- **Status:** Accepted for encrypted **new-archive** creation. Existing
  archives remain plaintext; no migration is implemented.
- **Date:** 2026-11-28
- **Scope:** Connection centralization and a synthetic SQLCipher prototype. No
  archive migration, key-storage product flow or production encryption claim.

## Context

HB Continuum currently stores `archive.sqlite3`, `research.sqlite3` and
`catalog.sqlite3` as plaintext SQLite databases. Connections were opened
directly with `sqlite3.connect` across the engine, IPC server, search, research,
intelligence, migrations, backup and the Tk search worker.

The encryption foundation must preserve existing behaviour, leave existing
archives untouched, and avoid any silent fallback from a requested encrypted
connection to plaintext.

## Connection inventory and centralization

All production connection paths now go through `hb_engine/db.py`:

| Area | Modules and paths |
|---|---|
| Email archive | `hb_engine/dispatch.py` (`Archive`), `hb_engine/ipc.py`, `hb_engine/unified.py`, `hb_engine/summarize.py`, `search_worker.py` |
| Research overlay | `hb_engine/research.py`, `hb_engine/intelligence.py`, `hb_engine/summarize.py` |
| Catalog | `hb_engine/catalog.py`, `hb_engine/dispatch.py`, `hb_engine/research.py`, `hb_engine/unified.py` |
| Search/query | `hb_engine/unified.py`, `hb_engine/advanced_search.py`, `hb_engine/ipc.py` |
| Migrations/snapshots | `hb_engine/migrations.py` |
| Backup/restore validation | `hb_engine/backup.py` |

Tests continue to construct plaintext fixtures with the standard library. The
central service delegates to `sqlite3` whenever no key is supplied, so existing
archives, tests and the packaged engine keep their current behaviour.

## Decision

Use **SQLCipher 4.20.0 community** through the maintained
[`sqlcipher3`](https://github.com/coleifer/sqlcipher3) Python binding, pinned in
verification to **0.6.5**.

- SQLCipher is licensed BSD-3-Clause; `sqlcipher3` is Zlib-licensed. Both are
  compatible with this project's GPL-3.0-only distribution.
- `sqlcipher3` 0.6.5 ships self-contained wheels, including
  `macosx_11_0_arm64` and Windows/macOS/Linux variants, with no external
  SQLCipher system library required.
- SQLCipher 4.20.0 reports FTS5 enabled. FTS5 tables, triggers, migrations,
  exact search and the native SQLite backup API worked in the prototype.
- The binding is optional. Plaintext use does not require it.

### Service contract

`hb_engine/db.py` exposes:

- `connect(path, key=None, timeout=30, uri=False, readonly=False)`.
- A 32-byte raw key selects SQLCipher. Text passphrases are rejected.
- The key is applied as a hex raw key before any query; key verification runs
  before the connection is returned.
- `readonly=True` applies `PRAGMA query_only=ON` after key installation.
- If a key is requested but `sqlcipher3` is unavailable, `EncryptionUnavailable`
  is raised. No plaintext connection is attempted.
- Missing or incorrect credentials cause SQLCipher to reject the database; the
  service closes the failed connection and propagates the error.
- `is_encrypted_file()` is a best-effort diagnostic for tests and tooling, not
  an authentication mechanism.

The prototype uses `os.urandom(32)` only in synthetic fixtures. Key generation,
key storage, key rotation and user authentication are deliberately not
implemented in this milestone.

## Verified prototype

A synthetic encrypted database was created and reopened with the correct key:

- A `CREATE TABLE` plus FTS5 virtual table succeeded; FTS5 matching returned the
  expected synthetic row.
- The file header was not `SQLite format 3\0`.
- Standard-library `sqlite3` could not read the file.
- The correct key opened it; a different 32-byte key and a missing key both
  failed.
- Read-only connection writes were rejected.
- The native `backup()` API produced a second encrypted database that reopened
  with the key and rejected a wrong key.
- Archive migrations 1 through 6 ran on an encrypted connection, and the
  resulting FTS5 index matched the inserted synthetic message.

Command used for the live check:

```sh
python3 -m venv /tmp/hb-sqlcipher
/tmp/hb-sqlcipher/bin/pip install sqlcipher3==0.6.5
/tmp/hb-sqlcipher/bin/python -m unittest tests.test_db
```

## Packaging check

`sqlcipher3` was installed in a temporary ARM64 macOS environment and PyInstaller
built a one-file encrypted smoke executable. The resulting Mach-O executable was
`arm64` and successfully created and reopened an encrypted FTS5 database.

The main engine build script now adds `--collect-all sqlcipher3` only when the
binding is installed. A packaged `hb-engine` built in that environment contained
`sqlcipher3/_sqlite3.cpython-313-darwin.so` and passed the existing engine smoke
test. Builds on machines without the binding remain plaintext-capable and do not
fail.

## Known limitations and next work

- No archive is encrypted or migrated. The three application databases remain
  plaintext by default.
- No key provider, OS keychain integration, passphrase KDF, key rotation or
  recovery workflow exists.
- SQLCipher exposes its own DB-API exception classes, which do not inherit from
  `sqlite3.Error`. Modules that catch standard-library exceptions need a shared
  exception abstraction before encrypted application databases are enabled.
- Backup, restore, snapshots and migration tooling accept plaintext connections;
  passing encryption keys through those workflows is future work.
- The prototype did not exercise a live GUI/Tauri encrypted archive, WAL under
  sustained concurrency, crash recovery, cross-platform ciphertext portability,
  or an exhaustive performance benchmark.
- SQLCipher's default cipher settings are used. No custom cryptography is
  implemented.

## Recommendation

SQLCipher via `sqlcipher3` is technically viable for a future encryption
milestone: licensing is compatible, FTS5 and migrations work, native backup
works, and ARM64 macOS packaging succeeds. The next milestone should add a
platform key provider, keyed constructors and a deliberately reversible
encryption/decryption migration with backup and recovery tests before any
production encryption claim.


## Update: encrypted creation milestone

`hb_engine/encryption.py` now creates a new archive in a staging directory and
publishes it atomically only after `archive.sqlite3`, `research.sqlite3`,
`catalog.sqlite3` and the public `.hb-encryption.json` KDF descriptor exist.
Passwords are prompted for, never placed in command-line arguments, and derived
to a 32-byte key with scrypt (`N=16384`, `r=8`, `p=1`, 16-byte salt). The key is
bound to the archive root only in process memory; explicit locking overwrites
the in-memory copy and prevents new connections.

SQLCipher encrypts the three databases and their rollback journals. Encrypted
connections use memory-backed temporary storage, secure deletion and SQLCipher
memory security. Raw EML files, external documents, preferences, schedules,
exports and reports remain plaintext. Encrypted backups are deliberately
refused until keyed backup/restore is designed and tested.

The desktop application includes an unlock panel and an explicit **Lock**
action; the IPC protocol exposes `encryption_status`, `encryption_unlock` and
`encryption_lock`. User-facing details and limitations are in
[Encryption](../ENCRYPTION.md).
