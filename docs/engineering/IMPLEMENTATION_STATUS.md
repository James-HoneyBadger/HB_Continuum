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
- Tauri 2 + Vue 3 desktop shell (`frontend/`, `src-tauri/`): a managed
  Python subprocess client driving `stats`, `search`, `message`, `thread`,
  `record`, `verify`, `import_eml`, `preferences`, and the full research
  overlay (workspaces, saved searches, tags, fields, metadata, reports with
  CSV export, rule rebuild), evidence export, and synchronization profiles
  (status, save, enable/disable, run-as-job); native open/save dialogs;
  frontend and Rust builds verified (working tree, uncommitted).

## Pending capabilities

See `BASELINE_AUDIT.md` section 9. In brief: versioned migrations,
packaged engine, desktop framework decision + PoC, local AI (Ollama
summarization/embeddings), source-independent catalog and adapters
(including Facebook JSON), unified search/timeline/research studio/Second
Me, cross-platform scheduling, packaging, documentation overhaul.

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

## Database changes

- New source-independent catalog database `catalog.sqlite3` with
  `source_files` and `records` tables plus a trigger-maintained FTS5
  `record_search` index, governed by a `PRAGMA user_version`-based migration
  sequence (v1 base schema, v2 search). The email archive schema is
  untouched by the Facebook importer.
- New `summaries` table in `research.sqlite3` (additive, via
  `CREATE TABLE IF NOT EXISTS`) with `input_digest` and `thread_members`
  companion columns for staleness detection and provenance.

## Migration considerations

- No migration framework exists. PR #4 introduces `attachment_index` and
  `extraction_versions` tables additively. A versioned, transactional,
  recoverable migration mechanism is required before further schema
  evolution.

## Tests executed

- `python3 -m py_compile` on changed files: pass.
- `python3 -m unittest discover -s tests`: 107 tests, all pass (29 baseline
  + 5 search-worker + 14 Facebook importer + 9 summarization + 4 unified
  search + 24 IPC + 22 scheduler).
- End-to-end CLI smoke tests of `dispatch facebook preview/import/search/
  list`, `dispatch summarize run --all` (fake loopback Ollama),
  `dispatch search-all`, and `dispatch serve` (subprocess protocol): pass.
- Frontend `npm run build` (vue-tsc + vite) and `cargo build` (Tauri):
  pass.
- `mypy` not run locally (not installed); CI runs `mypy` on Python 3.13.

## Test results

107 Python tests passed, 0 failed, 0 skipped (Python 3.12, Linux);
frontend and Rust builds pass; IPC surfaces smoke-tested end-to-end over the
real subprocess protocol (import, tag, workspace, saved search, field,
metadata, report preview, schedule profile). Scheduler strategies are tested
with mocked subprocess calls for all three platforms; real systemd/launchd/
schtasks installation was not exercised in this environment.

## CI status

- Existing workflows: `ci.yml` (py_compile, unittest on 3.12/3.13, mypy on
  3.13) and `codeql.yml` (Python analysis). Not re-run in this environment.
- Open PR #4 adds a macOS test matrix.

## Security findings

- No telemetry or hidden networking; network use is explicit (IMAP sync).
- Credentials excluded from preferences, backups, and Git.
- Tauri shell restricts capabilities to `core:default`, `dialog:allow-open`
  and `dialog:allow-save` (native dialogs only; no shell, filesystem, or
  HTTP plugins).
- Synchronization over IPC never accepts a password: the engine resolves
  credentials from the OS store at run time; no secret crosses the protocol.
- Symlink/path hardening and read-only backup connections exist only on
  PR #4; recommended for integration.

## Performance findings

- No benchmarks recorded. `timeline` performs a Python sort over filtered
  rows and is a known scaling risk beyond ~100k records.

## Known limitations

- No encryption at rest; no OAuth; HTML not rendered on `main` (PR #4 adds
  bounded HTML-to-text); no attachment search on `main`; no migrations.
- Cross-platform scheduling is implemented but only verified against mocked
  `launchctl`/`systemctl`/`schtasks`; real installation needs a desktop
  session (and a Windows runner for Task Scheduler).
- `sync_lock` is POSIX-only, so Windows has no archive-level write lock.

## Outstanding defects

- No versioned migration system.
- `sync_lock` is POSIX-only.
- Documentation identity is split between HB Dispatch (`main`) and HB
  Continuum (PR #5).

## Next recommended tasks

1. Scaffold the Tauri 2 + Vue 3 shell that spawns `dispatch serve` and
   drives `stats`/`search` (Rust and Node toolchains are available).
2. Support Facebook post/comment revision entries and message attachments
   metadata.
3. Add versioned migrations to `research.sqlite3`/`archive.sqlite3` before
   further schema evolution (the catalog now demonstrates the pattern).
4. Extend unified search with relevance-ranked cross-source fusion and
   date/kind filtering.
