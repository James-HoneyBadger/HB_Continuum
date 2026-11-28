# Encrypted archive creation

HB Continuum can create **new** archives whose three SQLite databases are
encrypted with SQLCipher 4.x. This is a creation foundation, not an encryption
upgrade for existing archives.

**Existing archives are not migrated.** Existing plaintext archives continue
to open exactly as before. There is no command that encrypts an existing
archive in place.

Existing archives can also be migrated to a new encrypted destination; see
[Encrypted archive migration](ENCRYPTION_MIGRATION.md). The original archive is
never deleted automatically.

## Create a new encrypted archive

The desktop archive chooser creates standard unencrypted archives. New
encrypted archives are currently created from the command line; existing
encrypted archives can then be opened and unlocked in the desktop application.

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

## Encrypted backup and restore

Encrypted archives can be backed up and restored without creating plaintext
database files:

```sh
python3 dispatch.py --archive ~/encrypted-archive backup ~/encrypted-backup
python3 dispatch.py verify-backup ~/encrypted-backup
python3 dispatch.py --archive ~/restored-encrypted restore ~/encrypted-backup
```

The source archive prompts for its archive password, and the backup prompts
for its backup password. The database files in the snapshot remain encrypted
with the same key. Raw EML files, configuration and reports copied into the
snapshot remain plaintext, and
the command prints that warning. There is no separate backup key or key
rotation.

The desktop Backup workspace supports the same operations when the current
archive is unlocked. A restored encrypted archive starts locked.

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

## Data boundary at a glance

Verified against the code, not copied from the release notes. "Inside" means
protected by SQLCipher on an encrypted archive.

| Data | Inside the SQLCipher boundary? | Where it lives | Supplementary control |
| --- | --- | --- | --- |
| SQLite databases | **Yes** | `archive.sqlite3`, `research.sqlite3`, `catalog.sqlite3` in the archive root | None needed beyond the passphrase |
| FTS5 indexes | **Yes** | Inside those three databases | None |
| Raw EML store | No | `<archive>/raw/<sha256>.eml` | Encrypted volume or container for the archive folder |
| External documents | No | Their original paths; the archive stores only extracted text and metadata | Encrypted volume, or keep originals on one |
| Configuration | No | `preferences.json`, `schedule.json`, `migrations` snapshots | Encrypted volume |
| Credential store | No | OS keyring, or `credentials.key` + `credentials.enc` in the archive directory when the insecure fallback is opted into | Keyring preferred; see [SECURITY.md](../SECURITY.md) |
| Exports and reports | No | The destination the user names | Encrypted volume; check before sharing |
| Logs | No | `boundary-notice.log`, scheduler status and diagnostics | Encrypted volume |
| Backups | Partly | Databases keep their encryption; `raw/`, configuration and reports in the snapshot do not | Treat a backup as plaintext unless every file in it is protected |

The in-app notice repeats this when an archive is opened; acknowledging it is
recorded once in `boundary-notice.log`.

## Can the raw store be brought inside?

Assessment, not a commitment. None of these ship in `v1.0.0`.

| Option | FTS5 indexing | Streaming large EML reads | Backup and restore | Migration cost | External readability | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| SQLCipher attached database holding EML blobs | Works: text is indexed from the same connection | Poor: blobs must be read through the database API; no plain file streaming | Simplest: one encrypted file family to copy | High: rewrite of ingest, verify, export and raw-hash checks | Lost: no file manager access | Not feasible now |
| Separate encrypted volume (APFS/FileVault, LUKS, BitLocker) | Unchanged | Unchanged: ordinary files | Unchanged, but the backup must stay on encrypted media | None | Kept, when mounted | **Feasible now, by the user** — documented below |
| Per-file AEAD blob store with a key from the archive passphrase | Works, with an extra decrypt step per file | Good: files decrypt to a temp path or stream | Medium: manifest plus key handling must cover many files | High: new on-disk format, key rotation, corruption handling | Lost without the tool | Feasible later |

Recommendation: use an encrypted volume for the archive directory today. That
protects raw EML, documents, configuration, exports and logs without inventing
a second cryptographic format. A per-file blob store would only be justified if
users need the archive to remain protected while it is detached and shared.

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
- **Backups**: encrypted-archive backup and restore keep the database files
  encrypted with the archive key. Raw EML files, configuration and reports in
  the snapshot remain plaintext. Backup/restore use the same archive password;
  there is no separate backup key or key rotation.
- **Local AI**: inference sends evidence to a loopback Ollama endpoint over
  HTTP. Loopback transport encryption is not added by this milestone.
- **Database descriptor** `.hb-encryption.json` is plaintext metadata. It
  reveals the KDF choice and salt, not the password or key.

Use full-disk encryption for the archive directory if the raw EML files,
external documents, configuration and exports must also be protected at rest.
See the [security threat model](SECURITY_MODEL.md) and macOS encrypted-volume
guidance there.

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
