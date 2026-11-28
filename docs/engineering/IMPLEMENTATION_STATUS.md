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
  search`/`facebook list` surfaces. Read-only catalog consistency checks
  (`facebook verify`, included in `health`) detect FTS drift, duplicate
  index rows, dangling source-file references and unreadable attachment
  metadata; `facebook reindex` rebuilds the record index. Catalog databases
  are now part of verified backups and restored archives.
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
  Responses report `total`, `total_is_exact` and `has_more` only when it is
  actually known. The 5000-fused-candidate listing cap introduced here was
  removed by the v0.5 paged search contract; see the v0.5 section below.
- The Search workspace gains source checkboxes, exact sender/actor, record
  kind and tag inputs, and states "at least" totals explicitly.
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
  existing attachment JSON into bounded searchable text; the catalog API also
  derives it whenever a caller supplies attachment JSON without the flattened
  text, and new imports populate it directly. Facebook, unified and advanced
  text search now match attachment names, titles, URIs, links and related
  metadata.
- Tests cover post versions and update times, comment actors and revisions,
  message attachments, post external/media/place attachments, the 100-entry
  cap, search by attachment metadata, catalog migration defaults, the v4→v5
  attachment FTS backfill, the IPC record response, API-level attachment
  indexing and detection/repair of index rows whose text drifted from the
  stored record.

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
  identifiers visible. The open item in the Search reader (message or catalog
  record) and the open message in the Timeline can also be added without first
  checking a result, using the same collection selector and optional note.
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

### Disabled-source visibility preference (2026-11-28)

- Research preference `hide_disabled_sources` (default off) hides records
  whose only known email accounts, or whose catalog source type, is disabled
  from unified search, the timeline and correspondent counts. Messages shared
  with an enabled account, `.eml`-only messages, the Sources inventory, the
  dashboard and explicit advanced queries remain unchanged; nothing is
  deleted or re-enabled.
- The IPC server reads the preference per request, so changing it applies to
  the next search or timeline load. The Preferences workspace renders and
  validates it through the existing schema.
- Tests cover email and catalog search and counts, shared-account and
  no-account messages, timeline and correspondent filtering, preference
  validation and the IPC toggle.

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
- Unified search streams each source index and merges lazily, so memory is
  bounded by the page size plus one buffered batch per source rather than a
  fixed candidate ceiling. Deep pages rescan from the start (offset
  pagination), so their cost is linear in the offset; a stateful cursor is a
  future optimization, not a current claim.
- 1,000,000-record runs have not been performed and are not claimed.

## Known limitations

- No encryption at rest; no OAuth. HTML is reduced to offline text but never
  rendered. PDF and DOCX email attachments are converted only when the
  optional local extractors are installed; image and legacy Office contents
  are not converted, so those attachments expose names, MIME types and any
  text payloads rather than their visual content.
- Cross-platform scheduling verified on all three operating systems via CI.
- Archive locking is implemented for POSIX and Windows and tested with real
  processes on macOS; the Windows code path has not yet run on Windows in
  this environment.
- The desktop shell now has a Source Manager with enable/disable, per-source
  verification and preview-first removal, import history, Collections with
  report drafts, a Journal, archive reports, the relationship explorer,
  nested boolean query groups and an Intelligence workspace with grounded
  research and validated citations. Unified search streams beyond the former
  candidate ceiling and supports cancellation in the desktop.
- Disabling a source stops new automatic imports. The optional
  `hide_disabled_sources` preference hides its records from default search,
  timeline and correspondent views; the Sources inventory, dashboard and
  explicit advanced queries retain them.
- Import history is best-effort for Facebook imports: a completed import
  reports `history_error` rather than failing when the run cannot be logged.

## Outstanding defects

- No encryption at rest and no OAuth; both are documented limits, not
  regressions.

## Next recommended tasks

1. Run the benchmark harness on Windows and Linux and add a 1M-record run
   before making large-archive claims.
2. Implement attachment content extraction and the remaining source
   registration/interchange interfaces.
3. Exercise intelligence against a live installed Ollama model and perform an
   interactive desktop acceptance run.

## Release qualification: v0.4.0-alpha (2026-11-27)

Feature freeze applies to this milestone. The following are deliberately
deferred: full conversational historical intelligence, semantic and hybrid
retrieval, expanded document ingestion, extensive Honey Badger ecosystem
interoperability, major architectural refactoring, and replacement of the
unified search pagination architecture.

Version metadata is aligned to `0.4.0-alpha` in the engine
(`hb_engine/dispatch.py`), frontend manifest and lockfile, Tauri configuration
and Cargo manifest and lockfile. The engine packaging smoke test now reads the
expected version from the engine source instead of a hardcoded string, and a
regression test fails if those manifests drift.

Verified locally on Python 3.12.0 and 3.13.7:

- `compileall` of the engine, tests, scripts and entry points: pass.
- `python -m unittest discover -s tests`: 280 tests, 278 passed, 2 skipped,
  zero failures on both versions.
- `mypy==2.4.1`: no issues in 23 source files.
- `npm run build` (Vue TypeScript check plus Vite production build): pass.
- `cargo check` and `cargo test` in `src-tauri`: pass, 3 unit tests.
- `scripts/scheduler_smoke.py`: installed, inspected and removed a real
  launchd entry; OK.
- `scripts/build_engine.py --no-copy --smoke`: PyInstaller one-file build
  passed CLI, search, health and IPC checks and reported `0.4.0-alpha`.
- `python3 dispatch.py --version`: `dispatch.py 0.4.0-alpha`.

The first hosted run exposed a test-only defect: the catalog health test left a
SQLite connection open through the transaction context manager, which blocked
temporary-directory cleanup on Windows. The test now closes it deterministically.
GitHub Actions `CI` run 46107292217 then passed all 12 jobs on commit `ef78643`:
Python 3.12 and 3.13 tests on Ubuntu, Python 3.13 on macOS and Windows, mypy,
frontend build, three engine smoke builds and three scheduler smoke runs.

No release tag or hosted release was created during the qualification pass itself.
The `v0.4.0-alpha` tag and GitHub prerelease were published afterwards, on
2026-11-28, from commit `10a8086`:
[releases/tag/v0.4.0-alpha](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.4.0-alpha).
The release is source-only; no signed binaries are attached. At that tag,
unified search still materialized at most 5000 candidate results per query
(superseded on the v0.5 development branch), and no 1,000,000-record run is
claimed.

## Release qualification: v0.4.0-beta (2026-11-28)

Promotes the v0.4.0-alpha qualification to beta. There are no functional
changes beyond version metadata. The feature freeze and deferred capabilities
listed in the alpha qualification remain in force.

Version metadata is now `0.4.0-beta` in the engine, frontend manifest and
lockfile, Tauri configuration, and Cargo manifest and lockfile. The existing
drift test verifies all five sources remain equal.

Re-verified for the beta on the qualification commit:

- Python 3.12.0 and 3.13.7: `compileall` passed; 280 tests, 278 passed,
  2 skipped, zero failures on both.
- `mypy==2.4.1`: no issues in 23 source files.
- `npm run build` (Vue TypeScript check plus Vite production build): pass.
- `cargo check` and `cargo test` in `src-tauri`: pass, 3 unit tests.
- PyInstaller engine build and smoke test: CLI, search, health and IPC passed;
  `hb-engine --version` reports `0.4.0-beta`.
- Tauri debug build with the engine sidecar: pass, sidecar reports
  `0.4.0-beta`.
- `scripts/scheduler_smoke.py`: installed, inspected and removed a real
  launchd entry; OK.
- `python3 dispatch.py --version`: `dispatch.py 0.4.0-beta`.

Hosted CI re-ran the full 12-job matrix after the version bump. The
`v0.4.0-beta` tag and GitHub beta release supersede the alpha as the current
milestone; the alpha remains flagged as a prerelease. The beta release is
source-only and includes no signed binaries.

## v0.5 Intelligence Update — Phase I: scalable unified search (2026-11-28)

Development branch: `develop/intelligence-update`, created from the verified
v0.4 beta development tip. The released tags are untouched.

- Unified search now streams each source index in rank order and merges the
  streams lazily. There is no fixed 5,000-candidate ceiling: a page is built
  by advancing only far enough to fill it, and the previous page size no
  longer bounds later results.
- Filters are applied before a record receives its rank. Within each source,
  ordering is deterministic by FTS5 relevance then record identifier; the
  merge then orders by reciprocal-rank score, parsed date, source and id.
  Parsed-date checks remain as a guard over the SQL filters.
- Exact totals still come from source count queries. A tag filter makes the
  total inexact, and the response reports that explicitly. The `capped`
  response field is retained for protocol compatibility and is always false.
- `search_job` runs the paged search as a cancellable background job through
  the existing job protocol. The engine also accepts an event-like `cancel`
  object on `search_unified_page`; a cancelled request returns its partial
  page flagged `cancelled` rather than presenting it as complete.
- The Search workspace now uses the job protocol, shows a Cancel button while
  searching, and no longer displays the removed candidate-cap warning. The
  Tauri `search` bridge now forwards sender, kind, tag and date filters that
  were previously dropped before reaching the engine; `search_job` is exposed
  with the same complete parameter set.
- Regression coverage creates a synthetic archive of 5,050 matching emails
  plus one catalog record and verifies: retrieval at offset 5,000, complete
  and duplicate-free collection across pages, deterministic page boundaries,
  sender and date filters before pagination, cancellation, malformed-query
  handling, and the IPC search job.
- Verified on Python 3.12.0 and 3.13.7: 291 tests, 289 passed, 2 skipped,
  zero failures on both; `mypy==2.4.1` clean on 23 files; frontend type-check
  and production build pass; `cargo check` and `cargo test` pass.

Remaining limitations for this phase: offset pagination rescans from the
start, so deep pages cost time proportional to the offset (memory stays
bounded); tag filters still make totals inexact; advanced boolean search
retains its separate safety bound and paging contract. The next milestone is
the evidence-grounded historical intelligence engine (Phases II and III).

## v0.5 Intelligence Update — Phases II and III: grounded research (2026-11-28)

- New `hb_engine/intelligence.py` separates request validation, retrieval,
  context assembly, Ollama transport, citation validation and conversation
  storage. That module is the only place that talks to a model; archive and catalog writes are never performed by it.
- Research requests are UI-independent and validated for question length,
  sources, date bounds, people/actors, topics, workspace, collection scope,
  retrieval depth (5–200), context budget (2,000–200,000 characters),
  per-record limit (200–10,000 characters), bounded history, optional model
  and conversation id.
- Retrieval builds bounded FTS5 expressions from the natural-language question
  and topics, searches each selected source, applies participant/date and
  collection filters before ranking, deduplicates matches across queries, and
  re-reads each record from its source database. Evidence carries source,
  record id, kind, title, actor, declared date, source location, retrieval
  score, full body, excerpt and complete/excerpt status. Retrieval remains
  useful with AI disabled.
- Context assembly keeps the highest-ranked evidence within the character
  budget, assigns stable evidence ids, orders records chronologically for the
  prompt, and reports omitted records and truncated excerpts instead of
  presenting a partial context as complete.
- The model prompt treats evidence as untrusted JSON data and explicitly
  forbids following instructions found inside it. Output is parsed into
  structured claims with evidence ids and epistemology labels. Citation ids
  are validated against the supplied evidence; invented ids and uncited claims
  are surfaced. Plain-text output is marked unstructured and is not treated as
  grounded. No model output can trigger tools, shell, filesystem or archive
  mutation.
- Ollama is loopback-only, no-redirect, no-proxy, streams NDJSON responses,
  checks cancellation between chunks, bounds response size, never pulls a
  model, and degrades to evidence-only results when disabled, unreachable or
  failing. Model discovery lists already-installed models.
- Research schema 6 adds `research_conversations` and `research_turns` in the
  research overlay. Conversations store questions, derived answers, validated
  citations, model names and timestamps; deletion cascades to derived turns
  and never affects source records. Export writes a JSON document outside the
  archive and refuses to overwrite.
- New IPC surface: `intelligence_status`, `intelligence_models` (job),
  `intelligence_retrieve`, `intelligence_ask` (cancellable job),
  `conversation_list`, `conversation_create`, `conversation_get`,
  `conversation_delete` and `conversation_export`. The Tauri bridge exposes the
  same commands.
- New desktop **Intelligence** workspace: conversation list, question input,
  source/date/people/topic/collection filters, depth/context/per-record and
  model controls, local AI status and model check, cancellable research,
  answer and claim display, rejected/uncited citation warnings, contradictions,
  missing information and limitations, retrieval-query inspection, evidence
  panel with direct record opening, conversation history, JSON export,
  conversation deletion, and saving an answer as a journal entry.
- Tests cover request validation, retrieval and source linkage, bounded context
  and omissions, accepted and rejected citations, unstructured output,
  insufficient evidence, disabled/unavailable/failing models, cancellation,
  prompt-injection handling, collection scope, conversation persistence and
  export safety, mocked Ollama streaming/model discovery, and the IPC surface.
- Verified: 313 tests, 311 passed, 2 skipped, zero failures on Python 3.12.0
  and 3.13.7; `mypy==2.4.1` clean on 24 files; frontend type-check and
  production build pass; `cargo check` and `cargo test` pass.

Remaining limitations: retrieval is keyword/FTS5 based rather than semantic;
contradiction and uncertainty labels are model-reported and only citation
identity is mechanically validated; no live Ollama model was exercised in the
automated suite; answer display is not token-streamed; no interactive desktop
acceptance run is claimed. The next milestone is Phase IV document ingestion
and broader catalog source registration.

## v0.5 Intelligence Update — Phase IV: document ingestion (2026-11-28)

- New `hb_engine/documents.py` imports local text, Markdown, CSV, JSON, PDF
  and DOCX into the existing catalog as `source_type='document'` records.
  Original files are hashed and referenced by path, never copied, uploaded or
  modified.
- Built-in extraction covers UTF-8/UTF-16 text, Markdown, CSV and validated
  JSON. PDF text and page references use the optional `pypdf` package; DOCX
  paragraphs and tables use optional `python-docx`. Without the package the
  preview and import report extraction as unavailable; they never pretend a
  binary was indexed as empty. Scanned PDFs without text are reported rather
  than OCRed. No macros, scripts or embedded document instructions execute.
- Limits: 50 MiB per file, 5,000,000 searchable characters (truncation is
  recorded), 1,000 page references, hidden files and symlinks skipped. Stored
  metadata includes path, hash, size, mtime, extractor, pages and explicit
  limitations.
- Imports are idempotent by SHA-256, changed files become later revisions
  under a stable document key, extraction failures are itemized, and every run
  is recorded in import history.
- Unified search and the Intelligence retrieval layer now treat `document` as
  a first-class source; catalog source selection can include `facebook` and
  `document`, and search results carry the actual source type. The advanced
  Boolean builder's catalog scope includes documents. The Tauri bridge and both
  the Search and Import desktop workspaces expose document source and import
  controls.
- Catalog health, source verification, disable/enable and preview-first
  removal apply to the `document` source through the existing catalog
  mechanisms. Removing documents never deletes the original files.
- Tests cover preview classification, text/Markdown/CSV/JSON indexing,
  duplicate skipping, revisions, extraction failures, import history,
  document-aware unified and advanced search, grounded retrieval, and missing
  paths.
- At that milestone: 319 tests, 317 passed, 2 skipped, zero failures on
  Python 3.12.0 and 3.13.7; `mypy==2.4.1` clean on 25 files; frontend
  type-check and production build passed; `cargo check` and `cargo test`
  passed.

## v0.5 Intelligence Update — Phase IV: email attachment text (2026-11-28)

- Email ingestion now sends PDF and DOCX attachments through the same local
  extractors used for standalone documents. Extracted attachment text joins
  the existing FTS body, so searches and grounded research can cite terms
  that occur only inside an attachment.
- Extraction is best-effort: a missing optional package, malformed file or
  encrypted PDF leaves the attachment metadata searchable and never rejects
  the surrounding message. The extractor version advances to 3, so the next
  `dispatch reindex` also retries older messages once.
- Attachment text remains bounded by the existing per-attachment and total
  limits; no attachment is written to a new location or executed.
- Tests cover PDF/DOCX text plumbing with mocked extractors, graceful
  unavailability, and reindex upgrade of an older extraction version.

## v0.5 Intelligence Update — Phase IV: document timeline (2026-11-28)

- The Timeline workspace can merge catalogued documents with email by
  recorded date. Rows carry their source and a record id, open in the catalog
  reader, and can be added to a collection like any other record.
- Documents remain omitted by default at the protocol level for compatibility;
  the desktop enables the merged view with **Include documents**. Sender
  filtering stays email-only, and the merged view is bounded to the first
  5000 entries so it cannot materialize an unbounded archive.
- Tests cover merged ordering, document-only pages, default compatibility and
  source validation.

Remaining limitations: PDF/DOCX extraction depends on optional local packages
and was not exercised against a live package in automated tests; OCR, page
navigation, layout/image preservation and semantic deduplication remain
unimplemented. Next: source-registration interfaces and Honey Badger
interchange (Phase V).


## Release qualification: v0.5.0-beta candidate (2026-11-28)

- Current manifests, the engine CLI and the packaged sidecar report
  `0.5.0-beta`. No v0.5 release or tag was created during qualification.
- Verified: scalable unified search (including pages beyond the former
  5,000-candidate ceiling), grounded research retrieval and conversation
  storage, document ingestion, PDF/DOCX email-attachment text, and merged
  document/email timelines.
- Defects corrected during qualification: the revision list now marks the
  latest stored version as current rather than the version being viewed;
  document preview no longer calls a file supported when its optional
  extractor is unavailable; advanced search accepts document-only scopes;
  document import closes its databases on early failure; reindex retries
  PDF/DOCX attachments after an optional extractor is installed; Ollama HTTP
  error responses are closed; document page references are labelled as pages
  instead of attachments.
- Verification results: 326 tests, 324 passed, 2 skipped, zero failures on
  Python 3.12.0 and 3.13.7; `mypy==2.4.1` clean on 25 files; Vue type-check
  and production build pass; `cargo check` and `cargo test` pass; packaged
  PyInstaller engine smoke passes and reports `0.5.0-beta`. Synthetic archive
  workflows exercised email, Facebook, document, unified search, advanced
  document-only search, document-aware timeline rows, grounded answers with
  citations, and conversation persistence.
- Live optional-extractor check: `pypdf` 7.2.0 and `python-docx` 1.2.0 were
  installed only in a temporary qualification environment. PDF and DOCX
  documents and email attachments produced searchable text there; CI does not
  install these packages.
- Remaining limitations: retrieval is keyword/FTS5 rather than semantic;
  OCR and PDF page navigation are absent; the merged timeline is capped at
  5,000 entries; optional extractors are not part of CI; no live Ollama model,
  interactive desktop acceptance run or exhaustive 1,000,000-record benchmark
  is claimed.
- Recommendation: **GO** for a source-only v0.5.0-beta publication by the
  owner, subject to those documented limitations. This is not a security
  certification or a claim of comprehensive platform support.

## Encryption foundation feasibility (2026-11-28)

- Production database connections now route through `hb_engine/db.py`.
  Without a key the service delegates to standard-library SQLite, preserving
  current archives and tests. With a raw 32-byte key it requires the optional
  `sqlcipher3` binding and never falls back to plaintext.
- SQLCipher 4.20.0 community was evaluated through `sqlcipher3` 0.6.5.
  Licensing is BSD-3-Clause plus Zlib, compatible with GPL-3.0-only. FTS5,
  migrations 1–6, read-only enforcement and the native backup API worked on
  synthetic encrypted databases.
- The ARM64 macOS wheel was packaged with PyInstaller using
  `--collect-all sqlcipher3`; the packaged executable created and reopened an
  encrypted FTS5 database. A packaged `hb-engine` built with the binding
  present passed the existing engine smoke test.
- Correct credentials opened the prototype; a wrong key, a missing key and
  plaintext SQLite all failed. No plaintext fallback occurred.
- Verification: 332 tests on Python 3.12.0 and 3.13.7. Without the optional
  binding, 328 passed and 4 skipped; with `sqlcipher3` installed in a temporary
  Python 3.13 environment, 330 passed and 2 skipped. `mypy==2.4.1` was clean on
  26 files. The packaged engine smoke test passed with and without the binding
  installed.
- Not implemented: archive encryption or migration, key generation/storage,
  OS keychain integration, key rotation, recovery, keyed backup/restore and
  migration workflows, a shared exception abstraction for SQLCipher's distinct
  DB-API exceptions, or any production encryption claim. Existing archives
  remain plaintext.
- Decision: SQLCipher is technically viable for a later encryption milestone.
  See [ADR-004](ADR-004-encrypted-databases.md).
