# Baseline audit — HB Continuum

Status: 2026-11-26. Author: engineering audit per the master directive.
Scope: repository state on `main` (v0.3.0), the two open pull requests
(#4 archive hardening, #5 continuum branding), and the uncommitted working
tree in the audit environment. This document records observed behavior, not
aspirational behavior.

## 1. Existing functional capabilities

### On `main` (v0.3.0, commit `e15964f`)

Core email archive engine (`dispatch.py`):

- Raw EML preservation: each imported message is stored byte-exact at
  `raw/<sha256>.eml`, mode 0700 directory.
- SHA-256 content addressing and exact-byte deduplication
  (`INSERT OR IGNORE` on the digest primary key).
- Plain-text body extraction (`text/plain` parts, attachments excluded).
- SQLite FTS5 keyword index over subject, sender, and body
  (`search` virtual table).
- Read-only IMAP sync: TLS, `BODY.PEEK[]`, UIDVALIDITY/UID tracking,
  per-folder batch cap, resumable across runs, origin conflict detection
  (`origins` table).
- Integrity verification (`verify`) recomputes hashes against raw files.
- Evidence export (`export`) writes selected EML plus `manifest.json` to a
  fresh, atomically-created directory.
- Query helpers: `find`, `recent`, `timeline`, `correspondents`,
  `thread` (Message-ID / In-Reply-To linkage), `details`, `stats`.
- CLI subcommands: `import`, `search`, `verify`, `export`, `sync`, `gui`.

Research overlay (`research.py`, `research.sqlite3`):

- Workspaces, saved searches, rule-based tagging, manual tags, custom
  fields (text/number/date/choice/boolean), metadata, CSV reports with
  formula-injection protection. Non-destructive: never writes
  `archive.sqlite3` or raw EML.

Desktop workstation (`desktop.py`, Tkinter):

- Search, recent view, reader pane (plain text only), conversation,
  timeline, correspondents, import, verify, export.
- Configuration center (`preferences_ui.py`), synchronization center
  (`schedule_ui.py`), research workbench (`research_ui.py`).

Scheduling (`schedule.py`):

- macOS-only background agent: launchd plist polling every 60 s; Keychain
  credentials via `/usr/bin/security`; profile add/pause/resume/run/tick.

Configuration (`preferences.py`):

- Versioned, validated, flat JSON preferences with defaults; GUI editor
  and portable export/import. No credentials in preferences.

### Open PR #4 — `develop/archive-hardening` (not merged)

- `backup.py`: offline archive snapshots (SQLite via backup API, raw EML,
  research overlay, config), SHA-256 manifest, integrity/foreign-key/index
  validation, restore-to-new-destination with schedules disabled.
- `mime_index.py`: bounded offline MIME extraction; HTML-to-text without
  rendering; attachment filename/MIME/text indexing; resource limits.
- `dispatch.py`: `health`, `reindex`, `recover-orphans`, `backup`,
  `verify-backup`, `restore` subcommands; symlink rejection; resolved paths;
  `busy_timeout`; `attachment_index` + `extraction_versions` tables;
  per-message resumable reindex.
- CI adds a macOS matrix; `tests/test_hardening.py` added (PR reports 40
  local tests passing).

### Open PR #5 — `chore/continuum-branding` (not merged)

- Rebrands user-facing text from HB Dispatch to HB Continuum while keeping
  `dispatch.py` as the mail-engine entry point, preserving archive paths and
  Keychain service names. Documentation and UI titles only.

### Working tree (uncommitted, this session)

- `search_worker.py`: background-thread GUI search (read-only SQLite
  connection, `queue.SimpleQueue` + `after()` polling, generation-based
  cancellation).
- `desktop.py`: search rewired off the UI thread; search button disable and
  indeterminate progress bar; window-close cancellation.
- `tests/test_search_worker.py`: parity and controller tests.
- `catalog.py`: source-independent catalog with `PRAGMA user_version`
  migrations and a trigger-maintained FTS5 search index.
- `facebook.py`: offline Facebook JSON importer (posts, comments, group
  posts, messages, events) with preview, provenance, resumability, and
  duplicate detection; `tests/test_facebook.py`.
- `summarize.py`: opt-in loopback Ollama message/thread summarization with
  prompt versioning, input-digest staleness detection, batch progress and
  cancellation; `tests/test_summarize.py`.
- `preferences.py` (AI settings), `research.py` (`summaries` table),
  `dispatch.py` (`facebook` and `summarize` subcommands).
- `ci.yml` / `mypy.ini`: include the new modules.

## 2. Partially implemented capabilities

- Attachment indexing: raw EML is preserved on `main` but attachment text
  is not searchable until PR #4; PR #4 indexes bounded text attachments but
  not PDF/Office/image content.
- HTML messages: not rendered by design; `main` extracts only `text/plain`,
  so HTML-only messages are unsearchable until PR #4.
- Backup/recovery: exists only on PR #4; no equivalent on `main`.
- Cross-platform scheduling: macOS only on `main`; Linux/Windows designed but
  unimplemented.
- AI: message/thread summarization is implemented (working tree); local
  embeddings/hybrid search and Second Me remain designed but unimplemented.
- Source independence: only email today; no adapter infrastructure.
- Desktop: Tkinter provides functional parity for core workflows, but search
  threading landed only in this working tree; thread/timeline/correspondent
  views, import, verify, and export remain synchronous on the UI thread.

## 3. Known defects

- No schema migration framework. Schema is created with
  `CREATE TABLE IF NOT EXISTS` in `Archive.__init__` and `Research.__init__`;
  PR #4 introduces `extraction_versions` as an ad-hoc marker rather than a
  general versioned migration system.
- `Archive` SQLite connections use the default `check_same_thread=True`;
  sharing a connection across threads raises `ProgrammingError`. The GUI
  search worker avoids this with a separate read-only connection, but the
  underlying constraint remains for any future off-thread archive work.
- `sync_lock.py` uses POSIX `fcntl`; on Windows it is a no-op, so scheduled
  or concurrent operations are not mutually excluded there.
- GUI operations other than search run synchronously on the Tk main thread;
  large `timeline`/`correspondents`/`verify` runs freeze the window.
- `verify` reads every raw file in full on the caller's thread; no progress
  reporting.
- No OAuth; provider app passwords only. Gmail OAuth is documented as
  future work.
- No encryption at rest; relies on OS/disk encryption.
- Documentation is stale in places: README still presents the HB Dispatch
  identity and v0.3.0 release while the product vision (and PR #5) moves to
  HB Continuum. No ROADMAP, ARCHITECTURE, SECURITY, CHANGELOG, or ADR
  documents exist.

## 4. Architectural weaknesses

- Single-file, unannotated modules: `dispatch.py` mixes storage, indexing,
  provenance, sync, and CLI in one class and `main()`. This works at the
  current size but resists the planned source-independent expansion.
- No package boundary (`src/continuum/...` does not exist); no
  `pyproject.toml` or dependency declaration.
- Two overlay databases already exist (`archive.sqlite3` and
  `research.sqlite3`), but there is no catalog/record abstraction for
  non-email sources; the email `messages` table is the de facto record
  table.
- Search is FTS5-only; the FTS5 `search` table embeds extracted text rather
  than pointing at a normalized record table, which complicates unified,
  source-independent search.
- No background-job abstraction; long-running work is either synchronous or
  ad-hoc threaded.
- The Tkinter UI duplicates query behavior (the GUI now re-implements
  `find`/`recent`/`stats` read-only queries in `search_worker.py`); this
  drift is guarded by an equality test but is still duplication.

## 5. Security considerations

- Local-first with no telemetry or hidden network access; network use is
  limited to explicit IMAP sync and (future) explicitly-enabled local AI.
- Raw EML is treated as untrusted input: parsed with `BytesParser` under
  `policy.default`; HTML is not rendered; exports never execute content.
- Report CSV export guards spreadsheet formula injection.
- Parameterized SQL throughout; user FTS expressions are passed to
  `MATCH` but arbitrary SQL is not possible.
- Preferences validation rejects unknown keys; credentials are never stored
  in preferences, config, Git, or backups (backup excludes Keychain).
- Weaknesses: no threat model document; PR #4 symlink/path checks and
  `mode=ro` backup connections are good but not yet on `main`; no CSP or
  IPC surface exists yet because there is no webview frontend.
- AI integration is not yet present, so its security boundaries are design
  requirements only at this point.

## 6. Performance considerations

- Import is O(1) per message after hash lookup; FTS insertion is indexed.
- `verify` and PR #4 `health` are O(total raw bytes) full scans.
- Search via FTS5 is efficient for the demonstrated ~20k-message archive;
  `timeline` sorts in Python (`sorted(...)`) over all rows matching the
  filter, which will degrade at 100k+ and should move to SQL ordering.
- No benchmarks exist; the directive requires synthetic 10k–1M scenarios
  before capacity claims.

## 7. Backward compatibility requirements

- `dispatch.py` must remain the CLI entry point; existing subcommands and
  the `--archive` default (`~/.hb-dispatch`) must keep working.
- Archive directory layout (`raw/`, `archive.sqlite3`, `research.sqlite3`,
  `preferences.json`, `schedule.json`) must not change incompatibly.
- Keychain service names and schedule profile shape must be preserved (PR
  #5 explicitly retains them).
- Migrations must be additive/non-destructive and tested against synthetic
  copies of older schemas — never against a real owner archive.

## 8. Test coverage

- `main` baseline: 29 tests (dispatch 14, preferences 4, research 4,
  schedule 7), all passing under Python 3.12 locally.
- Working tree: +26 tests (5 search-worker, 12 Facebook importer,
  9 summarization) = 55 passing.
- PR #4 reports 40 local tests on its branch; PR #5 reports 29.
- CI (`ci.yml`): Python 3.12/3.13, `py_compile`, `unittest discover`,
  `mypy` (3.13). PR #4 adds macOS to the matrix. CodeQL (Python) runs on
  push/PR/schedule.
- Gaps: no frontend tests (none exists), no security test suite, no
  performance benchmarks, no cross-platform scheduler tests.

## 9. Outstanding engineering work

1. Integrate or supersede PR #4 (hardening) and PR #5 (branding) — they
   change files also touched by this working tree (`desktop.py`, `mypy.ini`,
   `ci.yml`).
2. Reconcile the working-tree search-threading changes with PR #4/#5.
3. Extend the versioned migration mechanism to `research.sqlite3` and
   `archive.sqlite3` (the catalog now demonstrates the pattern).
4. Extract the engine into a package while preserving the `dispatch.py` CLI.
5. Decide the desktop framework (Tauri 2 vs PySide6/QML) via a working PoC.
6. Implement optional local embeddings/hybrid search with fake-server tests
   (summarization is done).
7. Implement source-independent catalog + adapters, then the Facebook JSON
   importer (catalog and Facebook posts/comments/messages/events are done;
   photos/videos/reactions and revisions remain).
8. Unified search, timeline, research studio, and Second Me.
9. Backup/recovery drills, cross-platform CI, packaging, and documentation
   overhaul.

## 10. Recommended implementation order

1. **Phase A (now):** this audit; confirm the merge/rebase strategy for
   PR #4 and PR #5; commit the tested search-threading increment.
2. **Stabilization:** land hardening + branding, then add versioned
   migrations and reconcile the search worker on top.
3. **Engine modularization:** package the engine behind the existing CLI;
   add typed interfaces and regression coverage.
4. **Desktop PoC:** evaluate Tauri 2 vs PySide6/QML on a small, real IPC
   prototype before committing; keep Tkinter until functional parity.
5. **Local AI:** preferences gate → Ollama backend → message/thread
   summarization → optional embeddings/hybrid search, all with fake-server
   tests and no cloud fallback.
6. **Source independence:** adapter protocol → catalog → Facebook importer
   → documents/journals/filesystem.
7. **Research workstation:** universal search, timeline, collections,
   people, reports.
8. **Second Me foundation:** controlled FTS5 retrieval + source-backed
   historical responses.
9. **Hardening:** security review, benchmarks, recovery drills,
   cross-platform validation, packaging, documentation.
