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
  extraction (integrated from closed PR #4).
- HB Continuum branding (integrated from closed PR #5).
- Source-independent catalog (`catalog.sqlite3`) with versioned migrations
  and an FTS5 search index, plus an offline Facebook JSON importer: posts,
  comments, group posts, messages, events, photos/videos, and reactions,
  with import preview, SHA-256 provenance, per-record original JSON
  preservation, idempotent resumable import, duplicate detection,
  post/comment revision metadata, attachment metadata, and `facebook
  search`/`facebook list` surfaces.
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
  and a reader; a Relationships tab shows observed co-participation in shared
  threads.
- Packaged engine (branch `develop/engine-expansion`):
  `scripts/build_engine.py` builds `dispatch.py` with PyInstaller into
  `dist/hb-engine` and copies it to `src-tauri/binaries/hb-engine-<host-triple>`
  for Tauri's `externalBin`; the shell resolves `HB_ENGINE`, then the bundled
  sidecar, then `HB_ENGINE_SCRIPT`/`dispatch.py` for development, with a clear
  startup error when none exists. A `--smoke` mode exercises the built binary,
  and CI builds and smoke-tests it on Ubuntu, macOS and Windows.
- Desktop shell client: drives `stats`, `search`, `search_advanced`, `message`,
  `thread`, `timeline`, `correspondents`, `relationships`, `record`, `verify`, `health`, `import_eml`,
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

### Search filters and honest totals (2026-11-27)

- Unified search accepts sender/actor, record-kind, date-range and tag
  filters alongside the FTS query. Sender and kind filters are applied in
  SQL for both sources; tags are resolved in the research overlay and applied
  to email results after ranking.
- Totals are exact counts from each source unless a tag filter is used.
  Responses now report `total`, `total_is_exact` and `capped`, and `has_more`
  only when it is actually known. The 5000-fused-candidate listing cap is
  exposed instead of being reported as a total.
- The Search workspace gains source checkboxes, exact sender/actor, record
  kind and tag inputs, and states "at least" totals and the listing cap
  explicitly.
- Malformed FTS expressions are now validated before running: the engine
  reports a specific rejection instead of silently returning no matches, and
  the Search workspace shows the reason plus syntax help (phrases, prefixes,
  uppercase boolean operators, grouping, NEAR). A human-readable summary of
  the active query and filters is shown above the results.
- Tests cover sender/kind/tag filters, exact counts, inexact tag totals,
  query validation and IPC validation.

### Facebook revisions and attachment metadata (2026-11-27)

- Catalog schema 4 adds `updated_at`, `revision_kind`, `revision_key`,
  `revision_index` and `attachments_json` to `records`, plus a
  `records_revision_key` index. Existing records keep their identifiers and
  search rows; the migration only adds columns.
- Posts and comments preserve declared `update_timestamp` (and `_ms`,
  `updated_timestamp`, `edited_timestamp`) as `updated_at`, with
  `post_update`/`comment_update` revision kinds. Distinct exported content
  versions remain separate records; a stable key based on source key and
  original timestamp groups them and an import-order index distinguishes
  versions. Comment authors are now stored as actors when present. The
  record response includes the other stored versions, and the Search detail
  view lets you open each version without merging their text.
- Message, post and comment attachment metadata is normalized into compact
  objects: photo/video/audio/file/gif/sticker/share/reaction, external link,
  place, event and marketplace. URIs, names, descriptions, thumbnails and
  timestamps are preserved; files are not copied. Each record stores at most
  100 attachment entries.
- The catalog record IPC response returns the new revision fields and parsed
  attachments, and the Search detail view labels attachment kinds and shows
  update/version metadata.
- Catalog schema 5 adds `attachments_text` and rebuilds `record_search` with
  `body`, `actor` and `attachments_text`. A migration callable flattens
  existing attachment JSON into bounded searchable text; new imports populate
  it directly. Facebook, unified and advanced text search now match
  attachment names, titles, URIs, links and related metadata.
- Tests cover post versions and update times, comment actors and revisions,
  message attachments, post external/media/place attachments, the 100-entry
  cap, search by attachment metadata, catalog migration defaults, the v4→v5
  attachment FTS backfill and the IPC record response.

### Saved advanced queries (2026-11-27)

- Research schema 5 adds `advanced_queries`: workspace-scoped name,
  description, serialized query tree, selected sources and timestamps, with a
  unique `(workspace, name)` pair and cascade from the workspace.
- The IPC boundary validates the tree with `normalize_query`, requires a group
  root so the graphical builder can load it, caps the stored JSON at 65,536
  characters and validates the selected sources. Saving an existing name
  updates it rather than creating a duplicate.
- The Advanced workspace gains workspace and saved-query selectors, Load,
  two-step Delete, a name/description form and Save. Loading replaces the
  builder tree, sources and form fields; the archive is not modified.
- Tests cover save/list/get/update/delete, workspace scoping, workspace
  cascade, unknown workspace, empty names, invalid sources, non-JSON and
  oversized trees, group-root enforcement, IPC validation and the full IPC
  surface.

### Engine package extraction (2026-11-27)

- The engine now lives in the `hb_engine` package: archive/CLI, IPC, catalog,
  migrations, research overlay, reporting, unified and advanced search,
  scheduling, scheduling backends, summarization, backup, preferences,
  Facebook import, MIME extraction and timestamp handling.
- `dispatch.py` is the unchanged CLI and PyInstaller entry point: it loads
  `hb_engine.dispatch`, calls `main()` and leaves `--version`, archive paths,
  command output and exit codes untouched.
- Top-level module names are compatibility aliases that replace themselves in
  `sys.modules` with the package module. Existing imports such as
  `from catalog import Catalog`, private test hooks and `mock.patch` targets
  therefore keep working against the same module identity.
- All engine cross-imports are package-relative, so a module is loaded once.
  The Tkinter workstation remains a presentation layer outside the package
  and imports `hb_engine.preferences`, `hb_engine.research` and
  `hb_engine.schedule`.
- `scripts/build_engine.py` passes `--collect-submodules hb_engine` so new
  engine modules are always included in the sidecar. CI compiles the package,
  root wrappers, tests and scripts, and mypy checks the package plus the Tk
  UI modules.
- Verified: 253 tests with no failures, CLI `--version`/`import`/`search`,
  a subprocess IPC `ping`/`shutdown` session, and a fresh PyInstaller 6.22.3
  sidecar rebuilt on macOS ARM64 with Python 3.13.7 after the final
  increments. `build_engine.py --no-copy --smoke` passed, including a real
  IPC session that asserts `search_advanced` returns both messages and
  `relationships` builds the thread edge. Tkinter was absent from the build environment; the Tauri shell
  does not use it.

### Advanced boolean queries (2026-11-27)

- `search_advanced` accepts a nested tree of groups (`and`, `or`, `not`) and
  rules: text, actor, kind, source, date and tag. The tree is validated for
  depth, node count, child count, value count and rule-specific fields; a
  malformed text expression is rejected by each selected index with syntax
  help instead of becoming an empty result.
- Rules evaluate as exact sets of `(source, id)` keys. AND intersects, OR
  unions, and NOT subtracts its single child from the selected-source
  universe, so negation is not a filter over an already-ranked page. Text
  rules carry reciprocal-rank scores; results sort by summed text relevance,
  then newest normalized date. Totals are exact and pagination reports
  `has_more`.
- Tag rules query the research overlay and therefore match email only; tags
  are explained in the response definitions. Date rules use a half-open
  `[after, before)` range and never match undated records. Snippets are
  truncated stored text.
- The Advanced workspace provides a recursive graphical builder: nested
  groups, rule-kind switching, source/kind checkboxes, inclusive date inputs
  and tag any/all mode. The sidebar lists it separately from unified Search.
- Tests cover nested AND/OR, exact NOT complements including nested NOT,
  metadata/date/source rules, undated handling, tag any/all, exact totals and
  pagination, global source scoping, validation messages, depth limits,
  malformed FTS and the IPC surface.

### Relationship explorer (2026-11-27)

- `relationships` builds a graph from observed co-participation only: two
  participants are linked when they appear in the same archived email thread
  (Message-ID / In-Reply-To component) or the same catalog conversation key
  (`record_kind='message'` grouped by `source_key`). Shared subjects, similar
  dates and address-book matches are never used as links.
- Node ids are prefixed with their source (`email|addr`,
  `facebook|name`), so an email address and a catalog actor are never merged
  into one identity. Each edge carries the number of shared threads, the
  messages involved and up to three example records.
- Caps keep the query bounded: 12 participants per thread, 100 nodes and 500
  edges. `truncated` reports when participants or edges were omitted. Date
  filters use normalized `sort_ts` and catalog `occurred_at`.
- The Relationships workspace shows a small SVG for up to 16 participants,
  a sortable-by-count table with examples, date and limit controls, and the
  definitions as visible text.
- Tests cover pairwise thread links, same-sender non-edges, separate
  threads, date filters, catalog conversations, cross-source identity
  separation, participant/edge truncation, an empty archive and IPC
  validation.

### Report drafts from collections (2026-11-27)

- Research schema 4 adds `report_drafts`, linked to a collection with
  cascade deletion. A draft stores a title, notes and timestamps; it is user
  annotation, not evidence.
- Draft exports render a chronology ordered by declared date (unknown last),
  the draft notes, an evidence-gaps section for missing references and
  explicit limitations, in Markdown, JSON or standalone HTML. Exports are
  written outside the archive and never replace an existing file.
- The Collections workspace gains draft create/edit/delete and export, with
  two-step deletion that states the collection and records are unaffected.
- Tests cover draft CRUD, collection cascade, chronology ordering, missing
  references, all three renderers, exclusive writing and the IPC surface.

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
search, Second Me, and the documentation overhaul
(ROADMAP/SECURITY/ARCHITECTURE/CHANGELOG).

Archive hardening, verified backup/restore, desktop health/backup surfaces,
Facebook import and the timeline explorer are implemented on
`develop/engine-expansion`; the Tkinter workstation remains the fallback
until the shell's flows are exercised against real archives.

## Architectural decisions

- Keep `dispatch.py` as the stable CLI and PyInstaller entry point while the
  engine implementation lives in `hb_engine`; top-level module names are
  compatibility aliases with the same module identity. Adopt "HB Continuum"
  as the overall product identity.
- Keep SQLite + FTS5 as the storage foundation; evaluate a separate catalog
  database for source-independent records without destabilizing
  `archive.sqlite3`.
- AI must be disabled by default and gated on explicit preferences; no
  cloud fallback; loopback endpoints only initially.
- Original records immutable; extracted text, research metadata, and machine
  summaries must be separated and distinguishable.

## Files changed

- Facebook-metadata increment (2026-11-27): `hb_engine/migrations.py`,
  `hb_engine/catalog.py`, `hb_engine/facebook.py`, `hb_engine/ipc.py`,
  `frontend/src/components/SearchView.vue`, `tests/test_facebook.py`,
  `tests/test_ipc.py`, `tests/test_migrations.py`,
  `docs/FACEBOOK_IMPORT.md`, `docs/MIGRATION.md`, `README.md`.
  Catalog version 5 followed in the same increment: `attachments_text`
  storage and the rebuilt attachment-aware FTS index.
- Saved-query increment (2026-11-27): `hb_engine/migrations.py`,
  `hb_engine/research.py`, `hb_engine/ipc.py`, `src-tauri/src/lib.rs`,
  `frontend/src/components/AdvancedSearchView.vue`,
  `tests/test_saved_queries.py` (new), `tests/test_migrations.py`,
  `docs/MIGRATION.md`, `README.md`.
- Engine-package increment (2026-11-27): `hb_engine/` (new package: 17 moved
  modules plus `__init__.py`), top-level compatibility aliases for every
  moved module, `dispatch.py`, `desktop.py`, `preferences_ui.py`,
  `research_ui.py`, `schedule_ui.py`, `scripts/build_engine.py`,
  `.github/workflows/ci.yml`, `mypy.ini`, `docs/PACKAGING.md`, `README.md`,
  `tests/test_build_engine.py`.
- Advanced-query increment (2026-11-27): `advanced_search.py` (new), `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/AdvancedSearchView.vue` (new),
  `frontend/src/components/QueryGroup.vue` (new),
  `tests/test_advanced_search.py` (new), `tests/test_ipc.py`,
  `docs/engineering/ADR-003-ipc-protocol.md`, `README.md`.
- Relationship increment (2026-11-27): `dispatch.py`, `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/App.vue`,
  `frontend/src/components/RelationshipsView.vue` (new),
  `tests/test_relationships.py` (new), `tests/test_ipc.py`, `README.md`.
- Draft increment (2026-11-27): `migrations.py`, `research.py`,
  `reporting.py`, `ipc.py`, `src-tauri/src/lib.rs`,
  `frontend/src/components/CollectionsView.vue`, `tests/test_collections.py`,
  `tests/test_ipc.py`, `tests/test_migrations.py`, `docs/MIGRATION.md`.
- Search-filter increment (2026-11-27): `unified.py`, `catalog.py`, `ipc.py`,
  `src-tauri/src/lib.rs`, `frontend/src/components/SearchView.vue`,
  `tests/test_unified.py`, `tests/test_ipc.py`.
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
  at version 5 and `research` at version 5. Archive version 2 adds
  `attachment_index` and `extraction_versions`; version 3 adds `sort_ts`,
  `date_precision` and the `messages_sort_ts` index (additive, with a
  transactional backfill); version 4 adds `import_runs` and its time index;
  version 5 adds `messages.size`, backfilled from the stored originals;
  version 6 adds `source_settings` and `source_events`. Research version 2
  adds `journal_entries` and `journal_revisions`; research version 3 adds
  `collections` and `collection_items`; research version 4 adds
  `report_drafts`; research version 5 adds `advanced_queries`. Catalog
  version 3 repairs the delete/update FTS triggers; version 4 adds revision
  and attachment metadata to `records`; version 5 adds `attachments_text`
  and rebuilds `record_search` to index it.
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

- `compileall` over `hb_engine/`, root wrappers, `tests/` and `scripts/`:
  pass. CI uses explicit compileall paths because PowerShell does not expand
  `*.py` globs.
- `python3 -m unittest discover -s tests`: 268 tests, 0 failures; optional
  credential-backend tests skip when `keyring` or `cryptography` are not
  installed (1 skip on the project Python 3.13 interpreter, 2 on a local
  Python 3.15 interpreter). Includes 8 timestamp/chronology tests, 2 real-process lock
  tests, 5 import-run tests, 6 journal tests, 8 collection/draft tests,
  5 report tests, 11 source management/verification tests, 11 unified-search
  tests, 10 advanced-query tests, 5 saved-query tests, 8 relationship tests,
  58 IPC tests, 19 Facebook tests, 5 benchmark tests and a packaging-smoke test.
- `mypy` 2.4.1 (matching CI): no issues in 23 source files, covering
  `hb_engine` and the Tk UI modules.
- `cargo test` (src-tauri): 3 tests pass, covering bundled-sidecar
  preference, the development script fallback and resolution from a bare
  directory.
- Bundled engine built locally with PyInstaller 6.22.3 (aarch64 Linux) and
  smoke-tested outside the repository: `--version`, `import`, `search`,
  `health` and an IPC `ping`/`health`/`shutdown` session all pass.
- Engine package sidecar rebuilt with PyInstaller 6.22.3 on macOS ARM64
  (Python 3.13.7) after the final increments: `--no-copy --smoke` passed,
  including the IPC checks for `search_advanced` and `relationships`.
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

268 Python tests ran: 0 failed; optional credential-backend tests skip when
`keyring` or `cryptography` are unavailable (1 skip on Python 3.13.6, 2 on
Python 3.15). `npm run build` (vue-tsc + vite), `cargo check` and `cargo test`
pass; background EML import, import history, sources, source removal, source
verification, journal, collections, reports, relationships, advanced queries
and the subprocess IPC protocol are covered by tests.

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

- Existing workflows: `ci.yml` (compileall, unittest on 3.12/3.13, mypy
  on 3.13, scheduler and packaged-engine matrices) and `codeql.yml` (Python
  analysis). The Windows compile step and benchmark harness were fixed after
  the first matrix run; see the latest branch run for the authoritative
  result.
- PR #4 (archive hardening) and PR #5 (branding) were closed as superseded
  on 2026-11-27. Their work is integrated in `develop/continuum-integration`
  (merges `0ce5454` and `6b83ffa` plus later fixes); the stale branches were
  not merged again.

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
  verification and preview-first removal, import history, Collections with
  report drafts, a Journal, archive reports, the relationship explorer and
  nested boolean query groups. Paged unified search beyond the current
  candidate cap remains pending.
- Disabling a source stops new automatic imports; it does not hide that
  source's historical records from search or the timeline.
- Import history is best-effort for Facebook imports: a completed import
  reports `history_error` rather than failing when the run cannot be logged.

## Outstanding defects

- No encryption at rest and no OAuth; both are documented limits, not
  regressions.

## Next recommended tasks

1. Extend unified search with a paged FTS contract so results are not
   capped at 5000.
2. Add collection selection from the timeline and record reader, and an
   optional "hide disabled sources from default views" preference.
3. Run the benchmark harness on Windows and Linux and add a 1M-record run
   before making large-archive claims.
