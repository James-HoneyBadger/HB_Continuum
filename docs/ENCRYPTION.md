# Encrypted archive creation

HB Continuum can create **new** archives whose three SQLite databases are
encrypted with SQLCipher 4.x. This is a creation foundation, not an encryption
upgrade for existing archives.

**Existing archives are not migrated.** Existing plaintext archives continue
to open exactly as before. There is no command that encrypts an existing
archive in place.

## Create a new encrypted archive

Choose a new or empty destination. Passwords must be at least 12 characters and
are entered twice through a hidden prompt; they are never passed on the command
line.

```sh
python3 dispatch.py --archive ~/encrypted-archive init-encrypted
```

This creates:

- `archive.sqlite3` — email, provenance, attachments index, import history.
- `research.sqlite3` — workspaces, tags, collections, journal, conversations.
- `catalog.sqlite3` — Facebook/document records, revisions and FTS index.
- `.hb-encryption.json` — public KDF descriptor: a random salt and scrypt
  parameters. It contains no password or derived key.

The destination directory is created atomically. If any database creation
fails, the staging directory is removed and no partial archive is published.

Requires the optional `sqlcipher3` package in the engine environment. A
plaintext build without it refuses encrypted creation rather than falling back
to plaintext.

## Unlock and lock

### Command line

When a command targets an encrypted archive, the CLI prompts for the password
using a hidden terminal prompt, derives the key in memory and uses it for that
process only:

```sh
python3 dispatch.py --archive ~/encrypted-archive search "invoice"
python3 dispatch.py --archive ~/encrypted-archive health
python3 dispatch.py --archive ~/encrypted-archive migrate
```

`dispatch.py --archive PATH encryption-status` reports whether the archive is
encrypted and whether the current process holds an unlocked session. It does
not need the password and does not expose key material.

### Desktop

Opening an encrypted archive shows a password panel. The password is used only
to derive the unlock key in memory; it is not written to preferences,
localStorage, logs or command-line arguments. The **Lock** button clears the
process key. Locking is refused while a background job is active; cancel the
job first.

### IPC

The engine protocol exposes:

- `encryption_status`
- `encryption_unlock` with a `password` parameter
- `encryption_lock`

These operate on the running engine process only. Closing the process or
locking explicitly discards the in-memory key.

## Key derivation and handling

- Password → 32-byte key using scrypt with a 16-byte random salt,
  `N=16384`, `r=8`, `p=1`, `dklen=32`.
- The salt and KDF parameters live in `.hb-encryption.json` with mode `0600`.
  They are not secret.
- The derived key is held only in process memory. The service copies it into a
  bytearray so an explicit lock can overwrite that copy.
- SQLCipher uses its established implementation. No cryptographic algorithm is
  invented by this project.
- Passwords are never stored in preferences, logs, Git, command-line arguments,
  localStorage or ordinary unprotected files.
- OS credential storage is not used in this milestone. No keychain consent
  prompt or persistent credential has been added.

There is no password change, key rotation, recovery key or password-reset
workflow. **If the password is lost, the encrypted databases cannot be
recovered by the application.**

## What is encrypted

- `archive.sqlite3`, `research.sqlite3` and `catalog.sqlite3`, including
  tables, indexes, FTS5 content, revisions and schema.
- The rollback journal used by these databases. SQLCipher encrypts database
  pages before writing them; the qualification test verified that a rollback
  journal does not contain a plaintext marker.
- SQLite temporary storage: encrypted connections set `temp_store=MEMORY`, so
  ordinary temporary database files are not created.
- SQLCipher memory security is enabled on encrypted connections.

Database copies made with ordinary SQLite, without the key, or with a wrong
32-byte key cannot be opened. The qualification tests verify all three cases.

## What remains unprotected

This milestone encrypts the three application databases only.

- **Original EML files** under `raw/` remain ordinary plaintext files. They are
  preserved for evidence and recovery, not encrypted by this milestone.
- **External documents** imported by path remain at their original locations
  and remain plaintext. HB Continuum does not copy them into the archive.
- **Preferences, schedules and configuration** files remain plaintext.
- **Exports and reports** written by the user remain plaintext.
- **Backups**: encrypted-archive backup and restore are not implemented in this
  milestone. `dispatch backup` and `dispatch restore` refuse encrypted archives
  rather than creating a plaintext copy.
- **Local AI**: inference sends evidence to a loopback Ollama endpoint over
  HTTP. Loopback transport encryption is not added by this milestone.
- **Database descriptor** `.hb-encryption.json` is plaintext metadata. It
  reveals the KDF choice and salt, not the password or key.

Use full-disk encryption for the archive directory if the raw EML files and
external documents must also be protected at rest.

## Session and artifact limits

- The key is process-local; there is no daemon-wide persistent unlock.
- Explicit lock clears the key and prevents new connections. The IPC server
  refuses to lock while background jobs are active. Direct library callers
  must not lock while they still hold an open database connection; close their
  connections first.
- SQLCipher uses its own DB-API exception classes, which are not subclasses of
  `sqlite3.Error`. Application code that catches standard-library SQLite
  exceptions must be adapted before encrypted archives become a general
  production path.
- No live GUI acceptance run, crash-recovery campaign, multi-process concurrent
  writer test or exhaustive performance benchmark is claimed.

## Packaging

The engine build includes `sqlcipher3` only when it is installed in the build
environment:

```sh
python3 -m venv /tmp/hb-encrypted-build
/tmp/hb-encrypted-build/bin/pip install pyinstaller sqlcipher3==0.6.5
/tmp/hb-encrypted-build/bin/python scripts/build_engine.py --smoke
```

The build script adds `--collect-all sqlcipher3`. Verify the packaged engine:

```sh
./dist/hb-engine --archive ~/encrypted-archive encryption-status
```

`available: true` means the packaged engine contains the SQLCipher binding.
Builds without the binding remain plaintext-only and refuse encrypted archive
creation or unlocking.
