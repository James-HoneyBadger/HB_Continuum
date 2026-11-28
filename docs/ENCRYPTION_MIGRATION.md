# Plaintext-to-encrypted archive migration

HB Continuum can migrate an existing **plaintext** archive to a new encrypted
archive. This is user-initiated and never deletes or modifies the source.

```sh
python3 dispatch.py --archive ~/plain-archive migrate-encrypted \
  --destination ~/encrypted-archive \
  --backup ~/plain-archive-backup
```

The command prompts twice for the new encrypted archive password. The password
is never taken from the command line or written to preferences, logs, Git or
ordinary files.

## Preconditions

- The source must contain `archive.sqlite3` and may contain
  `research.sqlite3` and `catalog.sqlite3`.
- The source and destination must be separate directory trees.
- The source and backup must be outside the destination, and the destination
  and backup must be separate.
- The destination must not exist or must be empty.
- The backup path must not already exist.
- The source database schemas must not be newer than this build.
- The optional `sqlcipher3` binding must be installed.
- The filesystem must have enough free space for the verified plaintext backup
  and the encrypted destination, with a safety margin.

## Process

1. Acquire the source archive's exclusive maintenance lock.
2. Check source schema versions and `PRAGMA quick_check`.
3. Check available space.
4. Create a plaintext backup with the normal backup/validation workflow.
5. Create an encrypted staging archive with the new password.
6. Export each source database into its encrypted counterpart using
   SQLCipher's `sqlcipher_export()`.
7. Apply any pending schema migrations to the encrypted copies.
8. Validate the encrypted copies:
   - schema objects and schema versions
   - table row counts
   - message hash lists
   - FTS5 table integrity checks
   - research collection/conversation table contents
   - `PRAGMA quick_check`
   - raw file SHA-256 hashes
9. Restore the plaintext backup to a temporary directory and independently
   validate the restored databases and referenced raw files.
10. Publish the verified encrypted destination atomically.
11. Release the maintenance lock and leave the destination locked.

The command exits successfully only after both the encrypted copy and the
restored backup pass validation.

## Failure and recovery

The original archive is **never** deleted or modified automatically. If a step
fails:

- the encrypted staging directory is removed;
- the destination is not published;
- the original archive remains usable;
- the plaintext backup remains available for inspection or recovery.

A failed backup or conversion can leave a hidden `.hb-migration-*` staging
directory under the destination parent after an abrupt process termination.
It is not treated as a valid archive. Inspect and remove it manually if needed.

To recover, continue using the original archive. Restore the verified plaintext
backup to another independent directory with:

```sh
python3 dispatch.py --archive ~/restored-archive restore ~/plain-archive-backup
```

The restored copy is plaintext. Do not point a production workflow at it unless
that is acceptable.

## Password loss

There is no password recovery or reset. If the encrypted destination password
is lost, that destination cannot be opened by HB Continuum.

The original plaintext archive remains available unless the operator chooses
to remove it. The migration does not remove it, and this milestone provides no
automatic cleanup command.

## Backups and legacy copies

The backup produced during migration is a **plaintext** snapshot. It contains
the databases, raw EML files and configuration at migration time.

Legacy backups, filesystem snapshots, sync copies, `.eml` exports and older
plaintext archives may continue to contain readable information after a
successful migration. Encrypting a new destination does not retroactively
encrypt those copies. Store and retire them deliberately.

Encrypted-archive backup/restore preserves encrypted database files and
requires the archive password. Raw EML files, configuration and reports inside
the snapshot remain plaintext. There is no separate backup key.

## What is encrypted

- `archive.sqlite3`, `research.sqlite3` and `catalog.sqlite3` in the
  destination.
- Their tables, indexes, FTS5 content, revisions and schema.
- Their rollback journals, which SQLCipher encrypts.
- SQLite temporary storage, which is memory-backed on encrypted connections.

## What remains unprotected

- Original EML files under `raw/` in the destination (copied from the source).
- External documents referenced by path; those files are not copied.
- Preferences, schedules and configuration files.
- User exports, reports and any plaintext backup.
- The public `.hb-encryption.json` KDF descriptor (salt and parameters only).
- Loopback Ollama HTTP traffic.

Use full-disk encryption or an encrypted APFS volume if raw EML files and
external documents must also be protected at rest. See the
[security threat model](SECURITY_MODEL.md) for macOS guidance and boundaries.

## Limitations

- No migration of already encrypted archives or key rotation.
- No OS keychain integration or password recovery.
- Encrypted backup/restore reuses the archive key; there is no independent
  backup key or key rotation.
- SQLCipher's DB-API exceptions are not subclasses of `sqlite3.Error`; shared
  exception handling remains future work.
- Validation compares row counts, hashes, FTS integrity and research table
  contents, but no migration is a substitute for independent archival review.
- The qualification suite uses synthetic archives only. No owner archive is
  accessed or migrated.

## Qualification results

- Synthetic migration tests cover a successful migration, source immutability,
  encrypted destination access, raw/config copying, ordinary-SQLite rejection,
  wrong-key rejection, insufficient storage, failed conversion, short password,
  failed restoration validation, CLI password confirmation and hidden-staging
  cleanup.
- Full suite: 347 tests, 329 passed and 19 skipped without the optional binding;
  345 passed and 2 skipped with `sqlcipher3` installed.
- The packaged ARM64 engine was built with `sqlcipher3`, migrated a synthetic
  plaintext archive, reported backup and restoration verification, retained the
  source, and searched the encrypted destination with the correct password.
- No owner archive was accessed or migrated.
