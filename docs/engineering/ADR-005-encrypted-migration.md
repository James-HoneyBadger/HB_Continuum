# ADR-005: Plaintext-to-encrypted archive migration

- **Status:** Accepted for explicit, user-initiated migration.
- **Date:** 2026-11-28
- **Scope:** Creating an encrypted destination from an existing plaintext
  archive. The source is never modified or deleted automatically.

## Decision

Migration uses SQLCipher's `sqlcipher_export()` to copy each source database
into an encrypted staging database. This preserves schema, triggers, virtual
tables, FTS5 content and data without reimplementing SQLite schema copying.

The source archive is held under its exclusive maintenance lock for the entire
operation. A plaintext backup is created and verified before conversion. The
destination is staged under a hidden directory and published atomically only
after validation and an independent restore check.

## Validated properties

- `archive.sqlite3`, `catalog.sqlite3` and `research.sqlite3` schema versions
  and `PRAGMA quick_check`.
- Schema objects required by the source are present in the encrypted copy.
- Table row counts and message hash lists match.
- FTS5 tables pass their integrity check.
- Research workspace, collection, journal, saved-query and conversation table
  contents match over common columns.
- Raw EML files copy with identical SHA-256 hashes.
- The plaintext backup restores to a temporary directory and its databases and
  referenced raw files validate independently.

## Safety properties

- The source is read through read-only connections.
- The source is never renamed, rewritten or deleted.
- Backup and destination must be outside the source and separate from each
  other.
- A destination that is non-empty is refused.
- Insufficient space, failed conversion, failed restore validation and invalid
  passwords leave the source untouched and do not publish a destination.
- The destination is locked after migration; the operator must unlock it
  explicitly.
- The backup is plaintext. Legacy backups, filesystem snapshots and old copies
  can remain plaintext indefinitely.

## Consequences

The migration is intentionally conservative and may require temporary space
for both the plaintext backup and encrypted destination. It does not provide
automatic deletion, key rotation, password recovery, in-place encryption or an
independent backup key. Encrypted backup/restore reuses the archive key;
raw/config files remain plaintext. SQLCipher's distinct
DB-API exception classes remain a future integration concern.
