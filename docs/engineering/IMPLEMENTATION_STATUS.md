# Implementation status — HB Continuum

Maintained per the master engineering directive (section 41). Updated
2026-11-27 on `develop/continuum-integration`.

## Current phase

Phase I — Consolidation and correctness, with the first Phase II shell work
landed (Overview dashboard, design tokens, timeline pagination).

## Implemented capabilities

- Email archival engine: raw EML preservation, SHA-256 addressing, dedup,
  IMAP origins, FTS5 search, verify, evidence export, resumable sync
  (`main`).
- Research overlay: workspaces, saved searches, rules, tags, custom fields,
  reports (`main`).
- Tkinter workstation: search, reader, conversation, timeline,
  correspondents, import, verify, export, configuration/synchronization/
  research centers (`main`).
- Background-thread GUI search with cancellation and progress indicator
  (working tree, uncommitted).
- macOS launchd + Keychain scheduling (`main`), extended to a portable
  scheduler (`schedulers.py`): systemd --user timers on Linux, Task Scheduler
  on Windows, and keyring/SecretService/Credential Manager credentials with
  an encrypted-file fallback; `dispatch schedule install|status|uninstall|
  credential` (working tree, uncommitted).
- Backup/recovery, health/reindex/orphan recovery, bounded MIME/attachment
  extraction (open PR #4, unmerged).
- HB Continuum branding (open PR #5, unmerged).
- Source-independent catalog (`catalog.sqlite3`) with versioned migrations
  and an FTS5 search index, plus an offline Facebook JSON importer: posts,
  comments, group posts, messages, events, photos/videos, and reactions,
  with import preview, SHA-256 provenance, per-record original JSON
  preservation, idempotent resumable import, duplicate detection, and
  `facebook search`/`facebook list` surfaces (working tree, uncommitted).
- Opt-in local AI summarization (`summarize.py`): loopback-only Ollama
  backend, strict `ai.enabled`/`ai.backend` gate, message and thread
  summaries with prompt versioning, input-digest staleness detection,
  batch progress/cancellation, and resumability; stored in
  `research.sqlite3` (working tree, uncommitted).
- Unified search (`unified.py`): keyword search across archived email and
  Facebook/catalog records via `dispatch search-all`, with source labels
  and plain-text snippets (working tree, uncommitted).
- Desktop IPC engine (`ipc.py`): versioned newline-delimited JSON protocol
  over stdin/stdout with `ping`, `stats`, paginated `search`, background
  `summarize` jobs with progress events and cancellation, and graceful
  `shutdown`; `dispatch serve` entry point (working tree, uncommitted).
- Database migrations: shared versioned, transactional `migrations.py` for
  `archive.sqlite3`, `research.sqlite3` and `catalog.sqlite3`, with a
  newer-schema guard, pre-migration snapshots, and
  `dispatch migrate [--dry-run] [--no-snapshot]`.
- Archive hardening (branch `develop/engine-expansion`, supersedes PR #4):
  bounded offline MIME extraction (`mime_index.py`) that turns HTML into
  plain text and indexes attachment names, MIME types and text; `archive`
  schema version 2 for `attachment_index` and `extraction_versions`;
  resumable `dispatch reindex`; `dispatch health` reconciliation of SQLite,
  foreign keys, index coverage and raw hashes; `dispatch recover-orphans`;
  verified `dispatch backup` / `verify-backup` / `restore` with SHA-256
  manifests; symlink and busy archive rejection; cooperative locking across
  ingest, sync, reindex, recovery and backup; attachment metadata, archive
  health (`health`) and resumable repair jobs (`reindex`,
  `recover_orphans`) over IPC, surfaced by a Health tab in the Tauri shell;
  schema reporting (`migrate_status`) and validated `backup`, `verify_backup`
  and `restore` jobs appear in a Backup tab, and both tabs consume forwarded
  engine events through a shared job composable; the Import tab offers
  Facebook export preview and background import alongside EML import; the
  Timeline tab shows chronological messages with per-correspondent counts
  and a reader.
- Packaged engine (branch `develop/engine-expansion`):
  `scripts/build_engine.py` builds `dispatch.py` with PyInstaller into
  `dist/hb-engine` and copies it to `src-tauri/binaries/hb-engine-<host-triple>`
  for Tauri's `externalBin`; the shell resolves `HB_ENGINE`, then the bundled
  sidecar, then `HB_ENGINE_SCRIPT`/`dispatch.py` for development, with a clear
  startup error when none exists. A `--smoke` mode exercises the built binary,
  and CI builds and smoke-tests it on Ubuntu, macOS and Windows.
- Desktop shell client: drives `stats`, `search`, `message`, `thread`,
  `timeline`, `correspondents`, `record`, `verify`, `health`, `import_eml`,
  `facebook_preview`/`facebook_import`, `preferences`, the full research
  overlay (workspaces, saved searches, tags, fields, metadata, reports with
  CSV export, rule rebuild), evidence export, synchronization profiles and
  backup/restore, with native open/save dialogs; frontend and Rust builds
  verified.

### Consolidation increment (2026-11-27)

- Fixed a real macOS defect found by a baseline run: a WAL-mode source could
  leave an empty `archive.sqlite3-shm` in a backup stage, so
  `validate_snapshot` rejected a correct snapshot. `copydb` now removes the
  normalized journal sidecars.
- Cross-platform archive write lock (`sync_lock.py`): POSIX `flock` and
  Windows `msvcrt.locking` on `sync.lock`, released by the operating system
  when a process dies. `schedule.tick` now uses the same primitive for its
  overlapping-run guard. Covered by real two-process tests, including a
  killed holder that must not leave a stale lock.
- Archive schema version 3 (`migrations.py`, `timestamps.py`): `sort_ts`
  (UTC epoch) and `date_precision` columns with an index, backfilled from the
  preserved date text by a migration callable. Timeline ordering moved from
  a Python sort over every row to indexed SQL with UTC-epoch date-range
  filters and pagination; unknown dates remain `NULL` and sort last. Unmigrated
  archives fall back to the previous in-memory order.
- Timeline pagination, oldest/newest ordering and a date range are exposed
  through IPC (`timeline` with `offset`, `order`, `after`, `before`), the
  Tauri command, and the Timeline workspace.
- `dashboard` IPC method and Overview workspace: unique messages, mailbox
  occurrences, undated records, earliest/latest normalized dates, catalog
  records, raw/database storage footprint, and records by year. Every figure
  has a documented definition; duplicates are not presented as unique
  records.
- Unified search now ranks each source with FTS5 `bm25` and fuses the two
  ranked lists with reciprocal rank fusion, instead of concatenating results
  and sorting by date. Optional `after`/`before` filters apply to both
  sources; the desktop Search workspace exposes a date range and page
  navigation.
- Honey Badger Contemporary Classic tokens (`frontend/src/theme.css`) and a
  shell (header, sidebar navigation, workspace, status bar). All component
  colours now come from the token file, and the Overview workspace is the
  default landing view. Text tokens were chosen to meet WCAG AA contrast on
  the workspace and panel backgrounds.

### Import history and Source Manager (2026-11-27, second increment)

- Archive schema version 4 adds `import_runs`, an append-only log with
  observed counts and status (`running`, `ok`, `cancelled`, `error`).
  EML imports, IMAP synchronization and Facebook imports write a run; a
  killed process is reported as interrupted rather than as success.
- `Archive.import_files` centralizes EML import for the CLI and the desktop
  engine: progress per file, between-file cancellation, per-file failures
  that do not abort the run, symlink rejection, and new/existing counts.
  The CLI `import` command uses it and gains `import-history`.
- `import_eml` is now a background IPC job with progress events and
  cancellation; the desktop exposes Cancel and shows real per-run history.
- New `sources` IPC method and Sources workspace: per-account messages,
  mailbox origins, folders, date coverage, last import status; catalog
  sources with records, files, bytes and coverage; storage footprint. The
  view states explicitly that importing folders never proves account
  completeness.
- Added the missing `cancel` Tauri command so the shell can cancel
  long-running engine jobs instead of only waiting for them.

### Journal workspace (2026-11-27, third increment)

- Research schema version 2 adds `journal_entries` and an append-only
  `journal_revisions` table. Creating or changing an entry writes a
  revision; an unchanged save writes nothing. Entries are soft-deleted and
  can be restored, with all revisions retained.
- `Research` exposes validated journal create/get/list/update/delete/restore
  operations with explicit bounds (200-character title, 1 MB body,
  ISO 8601 event date). The event date and the recording time are separate.
- IPC adds `journal_list`, `journal_get`, `journal_save`, `journal_delete`
  and `journal_restore`; the Tauri shell exposes matching commands.
- New Journal workspace: entry list, editor, revision history preview,
  two-step removal explanation and restore. The view states that entries are
  retrospective user records stored in the research overlay, never merged
  with preserved evidence.

### Evidence collections (2026-11-27)

- Research schema 3 adds `collections` and `collection_items`. A collection is
  a named, described evidence set in a workspace; items reference preserved
  records by content hash (email) or record id (catalog), with an optional
  note. Items are unique per collection and re-adding updates the note.
- Nothing is copied into the research overlay and deleting a collection never
  deletes archived records. A missing referenced record stays in the list and
  is marked missing.
- `collection_export` writes a Markdown or JSON evidence manifest with stable
  identifiers, titles, notes and explicit limitations (references, not
  contents; hashes are not legal certification). Manifests are written outside
  the archive and never replace an existing file.
- New Collections workspace: create/delete collections, inspect items with
  resolved titles, add by identifier, remove items and export a manifest.
  Search results can be added to a selected collection directly, keeping the
  identifiers visible.
- Tests cover membership, duplicate names, unknown records, missing-record
  reporting, cascade deletion and manifest rendering/writing.

### Source enable/disable and safe removal (2026-11-27)

- Archive schema 6 adds `source_settings` and an append-only
  `source_events` audit log. Disabling a source stops new automatic imports
  (including scheduled runs) while its historical records remain searchable
  and visible. Manual synchronization refuses a disabled account.
- `source_removal_preview` returns exact counts before anything changes:
  mailbox origins, unique messages deleted, shared messages retained, raw
  bytes freed, catalog records/files, and a plain-language explanation.
  Removal requires `confirm=true`; the IPC layer refuses otherwise with
  `CONFIRMATION_REQUIRED`.
- Email removal deletes only mailbox origins for the account and messages
  whose only account is that one. Shared messages keep their other origins;
  `.eml`-imported messages have no account and are untouched. Research
  annotations remain in the overlay (content-addressed hashes reattach on
  re-import). Files are removed after the transaction and any failure is
  reported rather than hidden.
- Catalog removal deletes that source type's records and file references;
  original export files on disk are untouched.
- Per-source integrity verification: `verify_source` checks only the message
  hashes reachable from one email account, or re-hashes the recorded export
  files for one catalog source where they still exist. It runs as a
  cancellable background job with progress and reports checked/verified/
  altered/missing counts; the Sources workspace shows the result and states
  that hashes are not legal certification.
- Found and fixed a real defect while implementing removal: catalog v2 used
  external-content FTS5 delete syntax on a contentful table, so deleting a
  catalog record failed with `SQL logic error`. Catalog schema 3 replaces the
  trigger; existing catalogs are repaired on open.
- Sources workspace adds status badges, Enable/Disable, a preview-first
  removal flow and recent source activity. Scheduled profiles skip disabled
  accounts as `disabled` without recording an attempt.
- Fixed a leaked archive connection when migration was refused by the
  archive lock (surfaced by ResourceWarning under the test suite).

### Benchmarks and stored original sizes (2026-11-27)

- Added `scripts/benchmark.py`, a deterministic synthetic benchmark harness
  for ingest, search, timeline paging, dashboard and peak memory, with an
  empty-directory safety rule and JSON output. Baselines are recorded in
  `docs/BENCHMARKS.md`.
- Archive schema 5 adds `messages.size`, recorded at import and backfilled
  from the raw files during migration. Dashboard/source/report storage
  totals now sum the column instead of walking every file, measured at 699 ms
  to 34 ms for 100,000 records. A missing size falls back to the scan.
- Benchmarks are covered by tests (determinism, workdir safety, measured
  structure), and CI compiles the harness.

### Safe automatic migration (2026-11-27)

- `Archive` now migrates under the archive write lock. When an existing
  archive has pending schema work, it writes a timestamped snapshot before
  touching the database; a brand-new database is not snapshotted, and an
  up-to-date archive still opens while another process works.
- `schedule.tick` treats an archive held by another operation as a
  deferral rather than crashing while opening the archive, preserving the
  documented "archive busy" behaviour.

### Archive reports (2026-11-27, fourth increment)

- New `reporting.py` renders an independently understandable archive report
  to Markdown, JSON or standalone HTML from inventory, dashboard, health and
  import-history data. Rendering is pure and HTML escapes every untrusted
  value.
- The report contains a summary, date coverage, records by year, email
  accounts, catalog sources, consistency counts, recent imports and explicit
  limitations. It states plainly that stored counts are not remote truth and
  that hash verification is not legal certification.
- `report_archive` is a background IPC job with progress and cancellation.
  It refuses destinations inside the archive, missing folders, a mismatched
  extension and any existing file; generation never overwrites.
- New Reports workspace: format selection, native save dialog, progress,
  cancellation and the written path/size. Add the report Tauri command.

## Pending capabilities

See `BASELINE_AUDIT.md` section 9. In brief: local embeddings/hybrid
search, Second Me, Facebook post revisions and message attachment metadata,
relationship explorer, and the documentation overhaul
(ROADMAP/SECURITY/ARCHITECTURE/CHANGELOG).

Archive hardening, verified backup/restore, desktop health/backup surfaces,
Facebook import and the timeline explorer are implemented on
`develop/engine-expansion`; the Tkinter workstation remains the fallback
until the shell's flows are exercised against real archives.

## Architectural decisions

- Preserve `dispatch.py` as a backward-compatible CLI wrapper and the email
  engine entry point; adopt "HB Continuum" as the overall product identity.
- Keep SQLite + FTS5 as the storage foundation; evaluate a separate catalog
  database for source-independent records without destabilizing
  `archive.sqlite3`.
- AI must be disabled by default and gated on explicit preferences; no
  cloud fallback; loopback endpoints only initially.
- Original records immutable; extracted text, research metadata, and machine
  summaries must be separated and distinguishable.

## Files changed

- Collections increment (2026-11-27): `migrations.py`, `research.py`,
  `reporting.py`, `ipc.py`, `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/CollectionsView.vue` (new),
  `frontend/src/components/SearchView.vue`, `tests/test_collections.py`
  (new), `tests/test_ipc.py`, `docs/MIGRATION.md`.
- Source-management increment (2026-11-27): `migrations.py`, `dispatch.py`,
  `schedule.py`, `ipc.py`, `src-tauri/src/lib.rs`,
  `frontend/src/components/SourcesView.vue`, `tests/test_sources.py` (new),
  `tests/test_ipc.py`, `tests/test_schedule.py`, `tests/test_migrations.py`,
  `tests/test_facebook.py`, `docs/MIGRATION.md`.
- Benchmark increment (2026-11-27): `scripts/benchmark.py` (new),
  `docs/BENCHMARKS.md` (new), `migrations.py`, `dispatch.py`, `ipc.py`,
  `tests/test_benchmark.py` (new), `tests/test_migrations.py`,
  `tests/test_timeline.py`, `tests/test_ipc.py`,
  `.github/workflows/ci.yml`.
- Migration-safety increment (2026-11-27): `dispatch.py`, `schedule.py`,
  `tests/test_migrations.py`, `docs/MIGRATION.md`.
- Reports increment (2026-11-27): `reporting.py` (new), `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/ReportsView.vue` (new),
  `tests/test_reporting.py` (new), `tests/test_ipc.py`,
  `.github/workflows/ci.yml`, `mypy.ini`.
- Journal increment (2026-11-27): `migrations.py`, `research.py`, `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/JournalView.vue` (new), `tests/test_journal.py`
  (new), `tests/test_ipc.py`, `tests/test_migrations.py`, `docs/MIGRATION.md`.
- Import increment (2026-11-27): `migrations.py`, `dispatch.py`, `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/ImportView.vue`, `frontend/src/composables/useEngineJob.ts`,
  `frontend/src/components/SourcesView.vue` (new), `tests/test_import_runs.py`
  (new), `tests/test_ipc.py`, `tests/test_migrations.py`,
  `docs/MIGRATION.md`.
- Consolidation increment (2026-11-27): `sync_lock.py`, `schedule.py`,
  `backup.py`, `migrations.py`, `dispatch.py`, `ipc.py`, `catalog.py`,
  `unified.py`, `mypy.ini`, `.github/workflows/ci.yml`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`, `frontend/src/main.ts`,
  `frontend/src/theme.css` (new), `frontend/src/components/OverviewView.vue`
  (new), `SearchView.vue`, `TimelineView.vue`, `HealthView.vue`, and every
  component's colour declarations; `timestamps.py` (new),
  `tests/test_timeline.py` (new), `tests/test_concurrency.py` (new),
  `tests/test_unified.py`, `tests/test_ipc.py`, `tests/test_hardening.py`,
  `tests/test_schedule.py`, `docs/MIGRATION.md`.
- Working tree (uncommitted): `desktop.py`, `dispatch.py`, `preferences.py`,
  `research.py`, `schedule.py`, `mypy.ini`, `.github/workflows/ci.yml`,
  `.gitignore` modified; `search_worker.py`, `catalog.py`, `facebook.py`,
  `summarize.py`, `unified.py`, `ipc.py`, `schedulers.py`, `frontend/`,
  `src-tauri/`, `tests/test_search_worker.py`, `tests/test_facebook.py`,
  `tests/test_summarize.py`, `tests/test_unified.py`, `tests/test_ipc.py`,
  `tests/test_schedulers.py` added.
- This session (documentation): `docs/engineering/BASELINE_AUDIT.md`,
  `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/FACEBOOK_IMPORT.md`,
  `docs/AI_SUMMARIZATION.md` added.
- Archive hardening (branch `develop/engine-expansion`): `mime_index.py`,
  `backup.py`, `tests/test_hardening.py`, `docs/ARCHIVE_HARDENING.md` added;
  `dispatch.py`, `desktop.py`, `ipc.py`, `migrations.py`, `mypy.ini`,
  `.github/workflows/ci.yml`, `README.md`, `docs/MIGRATION.md`,
  `frontend/src/App.vue`, `frontend/src/components/SearchView.vue`,
  `frontend/src/components/HealthView.vue`,
  `frontend/src/components/BackupView.vue`,
  `frontend/src/composables/useEngineJob.ts`,
  `frontend/src/components/TimelineView.vue`, `scripts/build_engine.py`,
  `docs/PACKAGING.md`, `src-tauri/tauri.conf.json`,
  `src-tauri/tauri.bundle.conf.json`, `facebook.py`,
  `frontend/src/components/ImportView.vue`, `src-tauri/src/lib.rs`,
  `tests/test_migrations.py`, `tests/test_ipc.py` modified.

## Database changes

- Schema versioning lives in `migrations.py`, shared by all three databases
  and tracked with `PRAGMA user_version`; `archive` is at version 6, `catalog`
  at version 3 and `research` at version 3. Archive version 2 adds
  `attachment_index` and `extraction_versions`; version 3 adds `sort_ts`,
  `date_precision` and the `messages_sort_ts` index (additive, with a
  transactional backfill); version 4 adds `import_runs` and its time index;
  version 5 adds `messages.size`, backfilled from the stored originals;
  version 6 adds `source_settings` and `source_events`. Research version 2
  adds `journal_entries` and `journal_revisions`; research version 3 adds
  `collections` and `collection_items`. Catalog version 3 repairs the
  delete/update FTS triggers.
- New source-independent catalog database `catalog.sqlite3` with
  `source_files` and `records` tables plus a trigger-maintained FTS5
  `record_search` index, governed by a `PRAGMA user_version`-based migration
  sequence (v1 base schema, v2 search). The email archive schema is
  untouched by the Facebook importer.
- New `summaries` table in `research.sqlite3` (additive, via
  `CREATE TABLE IF NOT EXISTS`) with `input_digest` and `thread_members`
  companion columns for staleness detection and provenance.
- No schema change for scheduling; `write_json` closes the temp file before
  `os.replace` (Windows requires this).

## Migration considerations

- Versioned, transactional migrations are implemented in `migrations.py` and
  documented in `docs/MIGRATION.md`. Snapshots are written before modifying a
  database that already contains data, and databases from a newer build are
  refused rather than opened.
- PR #4's `attachment_index` and `extraction_versions` tables are now
  `archive` version 2; its ad-hoc version marker and `executescript` schema
  setup are superseded and that PR should be closed rather than merged.

## Tests executed

- `python3 -m py_compile` on changed files: pass.
- `python3 -m unittest discover -s tests`: 222 tests, 221 pass and 1 is
  skipped on this machine (the optional `keyring` backend is not
  installed). Includes 8 timestamp/chronology tests, 2 real-process lock
  tests, 5 import-run tests, 6 journal tests, 6 collection tests, 5 report
  tests, 11 source management/verification tests, 6 unified-search tests and
  50 IPC tests.
- `mypy` (2.4.1, matching CI): no issues in 19 source files.
- `cargo test` (src-tauri): 3 tests pass, covering bundled-sidecar
  preference, the development script fallback and resolution from a bare
  directory.
- Bundled engine built locally with PyInstaller 6.22.3 (aarch64 Linux) and
  smoke-tested outside the repository: `--version`, `import`, `search`,
  `health` and an IPC `ping`/`health`/`shutdown` session all pass.
- Packaging layout verified with `tauri build --debug --no-bundle --config
  src-tauri/tauri.bundle.conf.json`: Tauri copied `hb-engine` next to the
  application, and the app launched under Xvfb spawned that engine and served
  `stats` (creating and migrating the archive databases over IPC).
- End-to-end CLI smoke tests of `dispatch facebook preview/import/search/
  list`, `dispatch summarize run --all` (fake loopback Ollama),
  `dispatch search-all`, and `dispatch serve` (subprocess protocol): pass.
- Frontend `npm run build` (vue-tsc + vite) and `cargo build` (Tauri):
  pass.
- End-to-end hardening smoke test on a temporary archive: `dispatch health`
  (clean exit 0), `dispatch backup`/`verify-backup`/`restore`, and
  `dispatch reindex` over a legacy v1 archive: pass.
- Desktop shell: `cargo check` and `npm run build` (vue-tsc + vite) pass
  with the health, repair, schema, backup and Facebook-import commands, the
  Backup tab and the forwarded `engine-event` channel.

## Test results

222 Python tests ran: 221 passed, 0 failed, 1 skipped (Python 3.13.6,
macOS ARM64); `npm run build` (vue-tsc + vite), `cargo check` and
`cargo test` pass; background EML import, import history, sources, source
removal, source verification, journal, collections and archive-report IPC
surfaces are covered by tests over the real subprocess protocol.

Scheduler verification status:

- **All three platforms verified for real** by
  `scripts/scheduler_smoke.py` in CI: systemd reached `active` on Ubuntu,
  `schtasks` reported `Ready` on Windows, and launchd reported `Loaded` on
  macOS — each with a real install, status check, secret-free file check and
  clean uninstall. Also verified locally on Linux (`systemd-analyze verify`
  clean, no residue).
- Cross-platform CI (Ubuntu/macOS/Windows) found and fixed three Windows
  defects: `os.replace` on an open handle in `write_json`, an unconditional
  `fcntl` import in `tick()`, and `os.getuid` reachable from tests.

## CI status

- Existing workflows: `ci.yml` (py_compile, unittest on 3.12/3.13, mypy on
  3.13) and `codeql.yml` (Python analysis). Not re-run in this environment.
- PR #4 (archive hardening) is superseded by the hardening work on
  `develop/engine-expansion`; PR #5 (branding) remains open and conflicts
  with this branch.

## Security findings

- No telemetry or hidden networking; network use is explicit (IMAP sync).
- Credentials excluded from preferences, backups, and Git.
- Tauri shell restricts capabilities to `core:default`, `dialog:allow-open`
  and `dialog:allow-save` (native dialogs only; no shell, filesystem, or
  HTTP plugins).
- Synchronization over IPC never accepts a password: the engine resolves
  credentials from the OS store at run time; no secret crosses the protocol.
- Symlink and path hardening now covers archive roots, raw originals,
  databases, snapshots and exports; backup validation opens databases
  read-only, and the Tauri shell still has no filesystem or HTTP plugin.

## Performance findings

- `scripts/benchmark.py` now produces a reproducible synthetic baseline
  (`docs/BENCHMARKS.md`). On macOS ARM64 with Python 3.13.6:

  | records | ingest | find p95 | timeline first | timeline deep | dashboard | peak RSS |
  |---|---|---|---|---|---|---|
  | 10,000 | 9.8 s (1,021/s) | 0.1 ms | 0.1 ms | 3.7 ms | 5.1 ms | 46.8 MiB |
  | 100,000 | 150.1 s (666/s) | 0.1 ms | 0.1 ms | 34.6 ms | 33.9 ms | 77.8 MiB |

- The first timeline page is constant-time; a deep page grows with the
  offset because SQLite walks the `sort_ts` index to the requested position.
  The archive is never loaded into memory.
- Storage accounting initially walked every raw file on each dashboard
  refresh (699 ms at 100k). Archive schema 5 records original sizes at
  import, reducing that dashboard to 34 ms while keeping a filesystem
  fallback for older or damaged archives.
- Unified search still materializes at most `SEARCH_CAP` (5000) fused
  results per query before paginating; that cap, not archive size, bounds
  memory. Raising it needs a paged FTS contract.
- 1,000,000-record runs have not been performed and are not claimed.

## Known limitations

- No encryption at rest; no OAuth. HTML is reduced to offline text but never
  rendered. PDF, Office and image attachment contents are not converted, so
  only attachment names, MIME types and text payloads are searchable.
- Cross-platform scheduling verified on all three operating systems via CI.
- Archive locking is implemented for POSIX and Windows and tested with real
  processes on macOS; the Windows code path has not yet run on Windows in
  this environment.
- The desktop shell now has a Source Manager with enable/disable, per-source
  verification and preview-first removal, import history, Collections, a
  Journal and archive reports, but still lacks the relationship explorer,
  research report drafts and a graphical advanced query builder.
- Disabling a source stops new automatic imports; it does not hide that
  source's historical records from search or the timeline.
- Import history is best-effort for Facebook imports: a completed import
  reports `history_error` rather than failing when the run cannot be logged.

## Outstanding defects

- Documentation identity is split between HB Dispatch (`main`) and HB
  Continuum (PR #5).
- No encryption at rest and no OAuth; both are documented limits, not
  regressions.

## Next recommended tasks

1. Extract the engine into a package behind the `dispatch.py` CLI and the IPC
   entry point, now that the packaged binary fixes the runtime contract.
2. Support Facebook post/comment revision entries and message attachments
   metadata.
3. Close PR #4 as superseded and reconcile PR #5 branding with this branch.
4. Extend unified search with a paged FTS contract so results are not
   capped at 5000, and add record-kind filters to the advanced query UI.
5. Add collection selection from the timeline and record reader, report
   drafts built from a collection, and an optional "hide disabled sources
   from default views" preference.
6. Implement the relationship/network explorer over documented associations.
7. Run the benchmark harness on Windows and Linux and add a 1M-record run
   before making large-archive claims.
