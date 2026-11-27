# Archive hardening and recovery

The archive separates original bytes from derived data: `raw/<sha256>.eml`
is never modified, while the FTS5 index, attachment text and research
overlays can be rebuilt. These commands inspect and repair the derived side,
and copy or restore the whole archive with verification.

Run them after stopping other writers (the workstation, scheduled
synchronization). Back up before upgrading, and use a destination outside
the archive, ideally on encrypted storage.

```sh
python3 dispatch.py --archive ~/HB_Mail_Archive health
python3 dispatch.py --archive ~/HB_Mail_Archive recover-orphans
python3 dispatch.py --archive ~/HB_Mail_Archive reindex
python3 dispatch.py --archive ~/HB_Mail_Archive backup /path/to/new-snapshot
python3 dispatch.py verify-backup /path/to/new-snapshot
python3 dispatch.py --archive /path/to/new-restored-archive restore /path/to/new-snapshot
```

## health

`health` prints a JSON diagnosis and exits non-zero when anything is wrong:

- SQLite `quick_check` and foreign-key results.
- Search-index coverage: messages without an index row, index rows without a
  message, and duplicate index rows for the same hash.
- Raw-file coverage: messages whose `.eml` is missing, `.eml` files that no
  message references, and files whose SHA-256 no longer matches.

Counts alone are not a completeness check against a provider: an IMAP
mailbox can hold messages that were never archived. `health` reports local
consistency, not remote coverage.

## recover-orphans

An interrupted ingest can leave a verified `.eml` file in `raw/` before its
database rows were committed. `recover-orphans` re-ingests files that are
hash-named, byte-verified and not oversized, and reports their hashes. It
never invents provenance: recovered messages have no mailbox origin until a
synchronization records one. Altered or oversized files are left in place
for investigation.

## reindex

Messages ingested by an older build may predate HTML-to-text extraction and
attachment indexing, and a damaged index can be missing rows or hold them
twice. `reindex` re-reads each affected original, verifies its SHA-256,
replaces the stored body and attachments, and rebuilds its search row in a
single transaction per message. It records progress in
`extraction_versions`, so an interrupted run resumes where it stopped. It
changes derived text only — original bytes and origin records are untouched.

Extraction is bounded and offline: HTML is reduced to text (scripts, styles
and markup are neither rendered nor executed), remote references are never
fetched, and attachment filenames, MIME types and text content are indexed up
to fixed limits. PDF, Office and image payloads are not converted.

## backup, verify-backup and restore

`backup` creates a new directory containing:

- `archive.sqlite3` and `research.sqlite3`, copied through SQLite's backup
  API with the journal normalised to a single file;
- `preferences.json`, `schedule.json` and `schedule-status.json` when present;
- every indexed `raw/<sha256>.eml` original;
- `backup-manifest.json` listing every file with its SHA-256.

The snapshot is built in a temporary staging directory, validated, and then
moved into place. Existing destinations are refused; symlinks and unexpected
files or directories fail validation. Validation re-checks hashes, SQLite
integrity, foreign keys, search-index coverage and the presence of every
original.

`restore` validates the snapshot and copies it to a new destination; it never
overwrites an existing archive, and it disables restored scheduling profiles
so a restored copy does not start background jobs. Keychain credentials are
not part of a snapshot and must be re-entered on the new copy.

Snapshots are not encrypted by the application. Use an encrypted destination
and treat the snapshot as sensitive as the archive itself.

## Cooperative locking

On POSIX systems, ingest, synchronization, reindex, orphan recovery, health
and backup take a cooperative `sync.lock`, so a manual import and a scheduled
one cannot overlap. This protects against this codebase only: older
executables, research overlays and arbitrary SQLite clients are not
coordinated. Windows has no equivalent archive-level lock yet; stop other
writers manually there.

## Remaining boundaries

No authenticity certification, legal hold, immutable audit storage,
multi-user authorization, malware sandbox or enterprise compliance claim is
made. A crash during final publication can leave a partial destination, so
verify every backup before relying on it, and never delete the source solely
because a backup command completed.
