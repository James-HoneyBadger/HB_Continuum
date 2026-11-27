# Migration and legacy compatibility

HB Dispatch keeps its data in three SQLite files inside the archive
directory. Schema changes are versioned, transactional and reversible in the
sense that the previous database file is preserved before any migration.

| Database | File | Purpose |
|---|---|---|
| `archive` | `archive.sqlite3` | Messages, FTS5 index, mailbox origins |
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
(schema 2, this build supports 1). Upgrade the application instead of
opening it with an older build.
```

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

1. Close every HB Dispatch window and stop scheduled synchronization
   (`python3 dispatch.py --archive ~/HB_Mail_Archive schedule uninstall`).
2. Copy the archive directory to a safe place.
3. Replace `archive.sqlite3` (or the affected database) with the snapshot:
   `cp archive.v0.backup.sqlite3 archive.sqlite3`.
4. Run `dispatch verify` to confirm original message bytes still match.

Snapshots are only taken when a migration actually applies; re-running
`migrate` on an up-to-date archive writes nothing.

## Backup recommendations

Schema snapshots are a migration safety net, not a backup strategy. Take a
full backup of the archive directory — `raw/` plus every database and
configuration file — with all writers stopped, on encrypted storage, and
test the restoration. Migration snapshots contain no `raw/` files, so they
cannot reconstruct an archive on their own.

## Adding a migration

1. Add the next integer version to `MIGRATIONS` in `migrations.py` for the
   affected database, using idempotent statements.
2. Prefer additive changes; avoid `DROP`/`ALTER` that discards data, and
   never reuse a version number.
3. Add a test in `tests/test_migrations.py` that builds the previous schema
   with representative rows, applies the migration, and asserts the data
   survives and the version advances.
4. Update this document and `docs/engineering/IMPLEMENTATION_STATUS.md`.
