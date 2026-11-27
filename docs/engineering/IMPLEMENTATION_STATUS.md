# Implementation status — HB Continuum

Maintained per the master engineering directive (section 41). Updated
2026-11-26.

## Current phase

Phase A — Stabilization (repository audit in progress).

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
  `recover_orphans`) over IPC, surfaced by a Health tab in the Tauri shell
  that consumes forwarded engine events.
  Python subprocess client driving `stats`, `search`, `message`, `thread`,
  `record`, `verify`, `import_eml`, `preferences`, and the full research
  overlay (workspaces, saved searches, tags, fields, metadata, reports with
  CSV export, rule rebuild), evidence export, and synchronization profiles
  (status, save, enable/disable, run-as-job); native open/save dialogs;
  frontend and Rust builds verified (working tree, uncommitted).

## Pending capabilities

See `BASELINE_AUDIT.md` section 9. In brief: packaged engine (PyInstaller or
equivalent) and sidecar bundling, local embeddings/hybrid search, Second Me,
backup and restore (blocked on PR #4), Facebook post revisions, timeline and
relationships explorers, and the documentation overhaul
(ROADMAP/SECURITY/ARCHITECTURE/CHANGELOG).

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
  `frontend/src/components/HealthView.vue`, `src-tauri/src/lib.rs`,
  `tests/test_migrations.py`, `tests/test_ipc.py` modified.

## Database changes

- Schema versioning moved to `migrations.py`, shared by all three databases
  and tracked with `PRAGMA user_version`; `archive` and `catalog` are at
  version 2 and `research` at version 1. Archive version 2 adds
  `attachment_index` and `extraction_versions` (additive; existing rows are
  untouched, and `dispatch reindex` upgrades older derived text).
- New source-independent catalog database `catalog.sqlite3` with
  `source_files` and `records` tables plus a trigger-maintained FTS5
  `record_search` index, governed by a `PRAGMA user_version`-based migration
  sequence (v1 base schema, v2 search). The email archive schema is
  untouched by the Facebook importer.
- New `summaries` table in `research.sqlite3` (additive, via
  `CREATE TABLE IF NOT EXISTS`) with `input_digest` and `thread_members`
  companion columns for staleness detection and provenance.
- No schema change for scheduling; `write_json` now closes the temp file
  before `os.replace` (Windows requires this).

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
- `python3 -m unittest discover -s tests`: 153 tests, all pass (29 baseline
  + 5 search-worker + 14 Facebook importer + 9 summarization + 4 unified
  search + 33 IPC + 26 scheduler + 1 Windows-path tick + 17 migrations + 15
  archive hardening).
- `mypy` (2.4.1, matching CI): no issues in 19 source files.
- End-to-end CLI smoke tests of `dispatch facebook preview/import/search/
  list`, `dispatch summarize run --all` (fake loopback Ollama),
  `dispatch search-all`, and `dispatch serve` (subprocess protocol): pass.
- Frontend `npm run build` (vue-tsc + vite) and `cargo build` (Tauri):
  pass.
- End-to-end hardening smoke test on a temporary archive: `dispatch health`
  (clean exit 0), `dispatch backup`/`verify-backup`/`restore`, and
  `dispatch reindex` over a legacy v1 archive: pass.
- Desktop shell: `cargo check` and `npm run build` (vue-tsc + vite) pass
  with the health/repair commands and the forwarded `engine-event` channel.

## Test results

153 Python tests passed, 0 failed, 0 skipped (Python 3.12, Linux);
frontend and Rust builds pass; IPC surfaces smoke-tested end-to-end over the
real subprocess protocol.

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

- No benchmarks recorded. `timeline` performs a Python sort over filtered
  rows and is a known scaling risk beyond ~100k records.

## Known limitations

- No encryption at rest; no OAuth. HTML is reduced to offline text but never
  rendered. PDF, Office and image attachment contents are not converted, so
  only attachment names, MIME types and text payloads are searchable.
- Cross-platform scheduling verified on all three operating systems via CI;
  Windows has no archive-level write lock (`sync_lock` is POSIX-only).

## Outstanding defects

- `sync_lock` is POSIX-only, so Windows has no archive-level write lock.
- Documentation identity is split between HB Dispatch (`main`) and HB
  Continuum (PR #5).

## Next recommended tasks

1. Surface backup, restore and migration status in the desktop shell; health
   and repair are now reachable over IPC and in the Health tab.
2. Support Facebook post/comment revision entries and message attachments
   metadata.
3. Close PR #4 as superseded and reconcile PR #5 branding with this branch.
4. Extend unified search with relevance-ranked cross-source fusion and
   date/kind filtering.
