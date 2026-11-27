# Migration and legacy compatibility

HB Continuum keeps its data in three SQLite files inside the archive
directory. Schema changes are versioned, transactional and reversible in the
sense that the previous database file is preserved before any migration.

| Database | File | Purpose |
|---|---|---|
| `archive` | `archive.sqlite3` | Messages, FTS5 index, mailbox origins, attachment index |
| `research` | `research.sqlite3` | Workspaces, tags, fields, reports, summaries |
| `catalog` | `catalog.sqlite3` | Source-independent records (e.g. Facebook) |

## Legacy Dispatch compatibility

- The archive directory layout is unchanged: `raw/<sha256>.eml`,
  `archive.sqlite3`, `research.sqlite3`, `preferences.json`,
  `schedule.json`, `schedule-status.json`.
- The command-line entry point and every existing subcommand keep working;
  `--archive` still defaults to `~/.hb-dispatch`.
- Existing archives created by v0.3.0 open directly. Their schema is
  identical to migration version 1, so upgrading records the version and
  changes no data.
- Keychain service names (`HB Dispatch IMAP <host>`) and schedule profile
  structure are unchanged, so existing credentials and schedules keep
  working.
- Configuration files are unchanged; no preference keys were renamed.

## How versioning works

Each database stores its schema version in SQLite's `PRAGMA user_version`.
Every migration version is a tuple of idempotent statements
(`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, …) applied in
one transaction together with its `user_version` bump.

Two consequences:

- Version 1 is both the baseline for a new database and the upgrade for a
  legacy one, so there is no separate "initialise" versus "upgrade" path.
- An interrupted migration leaves the database at the previous version,
  because the DDL and the version bump commit or roll back together.

Opening a database written by a **newer** build fails with a clear message
instead of proceeding, so an older binary cannot silently damage a newer
archive:

```
MigrationError: The archive database was written by a newer version
(schema 4, this build supports 3). Upgrade the application instead of
opening it with an older build.
```

A migration step may be a SQL statement or a Python callable that receives
the connection. Callables run inside the same transaction as the DDL and the
version bump, so a backfill and the schema that supports it commit together.

## Archive version 2: attachments and extraction tracking

Version 2 adds `attachment_index` (filename, MIME type and bounded text for
each MIME part) and `extraction_versions` (which messages were extracted by
the current extractor). Both are additive; existing rows, hashes and mailbox
origins are untouched.

Messages stored by an older build keep their previous body text until they
are re-extracted. `dispatch reindex` performs that upgrade from the preserved
raw originals, verifying each SHA-256 and committing per message, so it can
be interrupted and resumed. It also repairs search rows that are missing or
duplicated. See `docs/ARCHIVE_HARDENING.md`.

## Archive version 3: normalized chronology

Version 3 adds two nullable columns to `messages`:

| Column | Meaning |
|---|---|
| `sort_ts` | The declared date normalized to UTC epoch seconds, or `NULL` when it cannot be parsed |
| `date_precision` | `second`, `day`, or `NULL` for an unknown date |

An index (`messages_sort_ts`) supports chronological queries and pagination.
The migration backfills both columns from the preserved `date` text, so an
existing archive gains ordered timelines without re-importing anything. The
original `date` string is never rewritten; unknown or ambiguous dates remain
`NULL` rather than being guessed, and the timeline sorts them last.

New messages populate these columns during import. `dispatch reindex`
recomputes them from the stored date text while it re-extracts a message. A
read-only client that opens an older archive without migrating still gets a
correct (in-memory) order as a fallback.

## Archive version 4: import history

Version 4 adds `import_runs`, an append-only log of import attempts:

| Column | Meaning |
|---|---|
| `source` | `eml`, `imap` or `facebook` |
| `source_key` | Account, mailbox (with folder), or the selected paths |
| `started_at`, `finished_at` | UTC ISO 8601 timestamps; `finished_at` is empty while running or after a crash |
| `status` | `running`, `ok`, `cancelled` or `error` |
| `files_seen`, `records_seen` | What the run examined |
| `records_new`, `records_existing`, `records_failed` | Outcome counts |
| `detail` | Exception type for a failed run |

The log records observed counts only. A process killed mid-run leaves
`running`, which is reported as an interrupted attempt rather than being
silently rewritten as success. Nothing is backfilled for imports performed
before version 4; the UI reports history as unavailable for those runs.

## Inspecting and migrating

Opening the archive at all (`dispatch`, `dispatch gui`) migrates
automatically. To inspect first, or to migrate with a snapshot:

```sh
# Report versions and pending steps; changes nothing
python3 dispatch.py --archive ~/HB_Mail_Archive migrate --dry-run

# Migrate every database, writing a pre-migration snapshot first
python3 dispatch.py --archive ~/HB_Mail_Archive migrate

# Migrate without writing snapshots
python3 dispatch.py --archive ~/HB_Mail_Archive migrate --no-snapshot
```

Output reports `from`, `to`, `applied` versions and the snapshot path for
each database.

## Snapshots and rollback

With snapshots enabled (the default), each database that already contains
data is copied through SQLite's backup API to
`<name>.v<version>.backup.sqlite3` in the archive directory before it is
modified. The copy has the pre-migration version and contents.

To roll back:

1. Close every HB Continuum window and stop scheduled synchronization
   (`python3 dispatch.py --archive ~/HB_Mail_Archive schedule uninstall`).
2. Copy the archive directory to a safe place.
3. Replace `archive.sqlite3` (or the affected database) with the snapshot:
   `cp archive.v0.backup.sqlite3 archive.sqlite3`.
4. Run `dispatch verify` to confirm original message bytes still match.

Snapshots are only taken when a migration actually applies; re-running
`migrate` on an up-to-date archive writes nothing.

## Backup recommendations

Schema snapshots are a migration safety net, not a backup strategy. Use
`python3 dispatch.py --archive <archive> backup <destination>` for a full,
verified snapshot (`raw/` plus databases and configuration) and
`verify-backup` to re-check it later; see `docs/ARCHIVE_HARDENING.md`.
Store backups on encrypted storage and test restoring them. Migration
snapshots contain no `raw/` files, so they cannot reconstruct an archive on
their own.

## Adding a migration

1. Add the next integer version to `MIGRATIONS` in `migrations.py` for the
   affected database, using idempotent statements.
2. Prefer additive changes; avoid `DROP`/`ALTER` that discards data, and
   never reuse a version number.
3. Add a test in `tests/test_migrations.py` that builds the previous schema
   with representative rows, applies the migration, and asserts the data
   survives and the version advances.
4. Update this document and `docs/engineering/IMPLEMENTATION_STATUS.md`.
