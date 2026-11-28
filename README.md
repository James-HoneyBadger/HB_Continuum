# HB Continuum

**A local-first personal archive and historical research application.**

HB Continuum is an independent, open-source hobby project developed as part of the Honey Badger Universe.

Originally developed to preserve email correspondence, Continuum has gradually expanded to support other historical records, searchable documents, research tools and optional local artificial intelligence.

Its purpose is straightforward: help individuals preserve and explore their own documented history without depending entirely upon external service providers.

Development is iterative and driven by practical use. New features are introduced when they can be implemented, tested and maintained responsibly.

## Development priorities

- Reliable preservation and recovery of original information.
- Privacy and protection of sensitive archival records.
- Useful, dependable search and research capabilities.
- Optional local AI through Ollama.
- A straightforward desktop experience.
- Open formats and user-controlled information.

Continuum is maintained primarily by one developer as a personal FOSS undertaking. Development plans are flexible, and there are no commitments concerning delivery dates, comprehensive platform support or commercial service levels.

The longer-term idea of exploring one's documented past through local artificial intelligence remains an inspiration rather than a promise of future functionality.

Contributions, constructive feedback and independent development are welcome.

*The intelligence is replaceable. The memories are yours.*

## Your mail. Your archive. Your choice.

**Your email provider should be your communications service, not the permanent custodian of your correspondence.**

HB Continuum is built around personal digital sovereignty: keep your own searchable, locally controlled copy of your email history, independent of any hosting provider, subscription tier or cloud archive. Changing providers should not mean leaving years of correspondence behind.

The working archival workflow is simple: retrieve messages, preserve their original EML data, index them locally, verify their integrity, and maintain independent backups. Once archival and recovery have been verified, you can manage server storage separately from your long-term retention needs.

- Your correspondence, stored on hardware you control.
- Your search index, without a mandatory cloud service.
- Your retention decisions, rather than a provider's storage quota.
- Your backups, independent of the mailbox host.

HB Continuum is free and open-source software, licensed under the [GNU General Public License version 3 (GPL-3.0-only)](LICENSE). No telemetry, advertising, mandatory online account or subscription. It complements existing mail clients rather than requiring you to replace them.

**Important:** HB Continuum uses read-only IMAP retrieval and does not delete server mail. Keep independent backups and test restoration before removing any server copies. Comprehensive mailbox coverage and restoration testing remain essential; a successful import alone does not establish completeness.

## Learn by doing

**[Read the complete practical tutorial](docs/TUTORIAL.md).** Start with a fictional email, learn how the archive works, connect multiple providers, reconstruct historical correspondence, and build an independent backup routine. The guide distinguishes working capabilities from planned enhancements.

## A practical use case

**[From scattered inboxes to a personal historical intelligence archive](docs/USE_CASE_PERSONAL_HISTORY.md).** Follow a fictional user who combines years of correspondence across multiple providers, reconstructs forgotten events, prepares source-backed reports and explores an optional personal knowledge assistant. The scenario separates current archival capabilities from external analysis and future integrations.

## Quick start

Python 3.12+ with SQLite FTS5 and optional Tkinter for the legacy workstation. Building the Tauri desktop shell additionally requires Node.js 22+ and Rust.

```sh
python3 dispatch.py --version
python3 dispatch.py import sample.eml
python3 dispatch.py import-history
python3 dispatch.py search invoice
python3 dispatch.py verify
python3 dispatch.py health
python3 dispatch.py reindex
python3 dispatch.py backup /safe/snapshot
python3 dispatch.py migrate --dry-run
python3 dispatch.py gui
python3 dispatch.py sync imap.example.invalid user@example.invalid --folder INBOX
python3 dispatch.py export evidence HASH
python3 -m unittest discover -s tests -v
```

Source-independent imports and unified search use the same CLI:

```sh
python3 dispatch.py facebook preview ~/facebook-export
python3 dispatch.py facebook import ~/facebook-export
python3 dispatch.py facebook search "receipt"
python3 dispatch.py documents preview ~/documents
python3 dispatch.py documents import ~/documents
python3 dispatch.py search-all "receipt"
```

For mailbox names containing spaces, use normal shell quoting, e.g. `--folder "Sent Items"` or `--folder "Sent Messages"`. HB Continuum quotes the IMAP mailbox internally and recognizes origins recorded by older versions with literal surrounding quotes.

Use `--archive PATH` before the subcommand to select storage. Sync uses TLS, read-only mailbox selection and BODY.PEEK. Passwords are prompted for, never stored by the application. Provider-specific authentication may be required. Gmail OAuth and a native MCP integration remain future work. Manual synchronization prompts for passwords; scheduled synchronization supports platform-specific schedulers and credential stores.

## Engine layout

The engine implementation lives in `hb_engine/`, with the CLI, IPC server, archive, catalog, research overlay, migrations, search and local intelligence modules sharing one package. `dispatch.py` remains the command-line and PyInstaller entry point, and the historical top-level module names are compatibility aliases, so existing scripts and tests keep the same imports.

The archive uses three SQLite databases: `archive.sqlite3` for email, origins, the email FTS index and import history; `research.sqlite3` for workspaces, tags, metadata, collections, journal entries and reports; and `catalog.sqlite3` for source-independent records, revisions, attachment metadata and the record FTS index. Versioned, transactional migrations upgrade them in place, and opening a database written by a newer build is refused rather than risking damage.

## Privacy and limitations

Original EML files are preserved by SHA-256 with SQLite search and mailbox provenance. Hashes detect changes, not authenticity or certified chain of custody. No telemetry or sending. HTML is not rendered. Use an encrypted disk and keep all real mail and credentials outside the repository. Verify backup and restore with `dispatch backup`, `dispatch verify-backup` and `dispatch restore`, and diagnose local consistency with `dispatch health` (see [Archive hardening](docs/ARCHIVE_HARDENING.md)). Failed imports may leave unindexed raw files; `dispatch recover-orphans` and `dispatch reindex` repair them from the preserved originals. Failed exports may be partial. Live IMAP retrieval has been demonstrated with IONOS, Gmail and iCloud Mail; comprehensive GUI, provider compatibility, hostile-MIME and restoration testing remain ongoing. Search indexes plain-text bodies, HTML reduced to offline text, and attachment names, types and bounded text. Optional document extraction adds searchable PDF and DOCX text; scanned images are not OCRed, and PDF/Office attachment contents inside email are not converted. Facebook exports are read in place and never modified; the catalog preserves original record JSON, revision identity and attachment metadata, not attachment bytes. Optional local AI summaries and research answers are derived text: historical evidence is treated as untrusted data, and model output cannot modify the archive. Exact-byte deduplication does not guarantee semantic deduplication across providers. Do not use HB Continuum as the sole evidence archive.

## Scheduled synchronization

Maintain multiple mailboxes automatically with the local synchronization center, configurable interval or daily schedules and platform-specific credential stores. See [Scheduled synchronization](docs/SCHEDULED_SYNC.md). Finish any older manual import before enabling the service.

## Configuration center

Customize the workstation per archive with validated, portable settings for appearance, research, file locations, integrity checks and synchronization. Open **Configuration center** in the desktop application. See [Configuration reference](docs/CONFIGURATION.md).

## Research workbench

Create workspaces, saved queries, classification rules, tags, custom metadata and reusable CSV reports without changing original correspondence. See [Research workbench](docs/RESEARCH.md).

## Import center, history and source manager

Desktop imports run as cancellable background jobs with real progress. Every EML, IMAP, Facebook and document import appends a run to the archive's import history, recording what was examined, what was new, what already existed and what failed. A killed process is reported as interrupted rather than rewritten as success.

The Sources workspace derives coverage from stored provenance: unique messages and mailbox occurrences per account, folders read, normalized date coverage, last import status, catalog sources and storage footprint. It states explicitly that importing folders never proves an account is complete. Importing `.eml` files preserves messages without inventing an account.

Each account or catalog source can be verified independently: email checks are scoped to that account's messages, and catalog verification re-hashes the recorded export files where they still exist. Verification runs in the background with progress, cancellation and explicit altered/missing counts.

Sources can be disabled — stopping new automatic imports while every historical record stays searchable — and re-enabled. Removal is preview-first: HB Continuum counts the unique messages, shared duplicates and raw bytes involved and explains what will be kept before anything is deleted. Messages shared with another account, and messages imported from `.eml` files, are never removed by an account removal. Removing a catalog source deletes its catalog records, not the original export files. See [Migration and compatibility](docs/MIGRATION.md) for the schemas and audit log.

A research preference can hide records from disabled sources in unified search, the timeline and correspondent counts without deleting or re-enabling anything. Messages shared with an enabled account, `.eml`-only messages and explicit advanced queries are unaffected.

## Intelligence workspace

Ask natural-language questions about your documented history and inspect the records behind each answer. Retrieval works without any model: the engine builds bounded local queries, applies source, date, participant and collection filters, and returns source-linked evidence with stable identifiers, excerpts and explicit omission/truncation notices. With a local Ollama instance enabled, answers must return structured claims with evidence identifiers; citations that were not actually supplied are rejected and uncited claims are flagged. Contradictions, missing information and uncertainty are shown separately, and every cited record opens in the reader. Conversations live only in the research overlay and can be exported or deleted without touching evidence. AI remains disabled by default. See [Intelligence](docs/INTELLIGENCE.md).

## Evidence collections

Group selected records into named collections inside a research workspace. Items are references to preserved records — SHA-256 hashes for email, record ids for catalog entries — with optional notes. Nothing is copied into the research overlay, and deleting a collection never deletes an archived record. A referenced record that disappears stays listed and is marked missing. Collections export as Markdown or JSON evidence manifests with stable identifiers, notes and explicit limitations, and never replace an existing file. Selected search results, the open record in the Search reader and the open message in the Timeline can be added to a collection directly.

A collection can also hold **report drafts**: titled notes that render a chronology ordered by declared date, evidence gaps for records that have gone missing, and explicit limitations. Drafts export as Markdown, JSON or standalone HTML, are stored as user annotations rather than evidence, and never replace an existing file.

## Relationship explorer

The Relationships workspace links participants only when they appear together in the same archived email thread (Message-ID / In-Reply-To) or the same catalog conversation. It never infers a relationship from a shared subject, a similar date or an address-book match. Email addresses and catalog actor names stay separate identities, each edge lists the shared threads, message counts and example records, and 12 participants per thread, 100 nodes and 500 edges are hard caps with explicit truncation. A shared thread is co-participation, not proof of any personal or causal connection.

## Journal and archive reports

The Journal stores your own retrospective entries in the research overlay, separate from preserved evidence. Every edit adds a revision; saving without changes adds nothing. Removal is soft, so history stays inspectable and the entry can be restored.

The Reports workspace writes a self-contained Markdown, JSON or standalone HTML archive report: summary, date coverage, records by year, email accounts, catalog sources, consistency checks, recent imports and explicit limitations. Reports are written outside the archive, never replace an existing file, and state that stored counts and hash checks are not remote truth or legal certification.

## Performance baseline

`scripts/benchmark.py` builds deterministic synthetic archives and measures ingest, search, timeline paging, dashboard and peak memory. Current baselines and reproduction steps are in [Benchmarks](docs/BENCHMARKS.md). The harness never touches a real archive and refuses a non-empty work directory.

## Source-independent records and research

Beyond email, the following capabilities are implemented. Facebook ingestion is opt-in; local AI is disabled by default.

**Facebook import** — import posts, comments, group posts, messages, events, photos/videos, and reactions from a user-obtained Facebook JSON export. Post/comment update timestamps and revision versions are preserved, and message/post attachment metadata is stored and searchable without copying media files. Original exports are never uploaded or modified. See [Facebook import](docs/FACEBOOK_IMPORT.md).

```sh
python3 dispatch.py facebook preview ~/facebook-export
python3 dispatch.py facebook import ~/facebook-export
python3 dispatch.py facebook search "receipt"
python3 dispatch.py facebook list --kind event
```

**Document import** — import local text, Markdown, CSV, JSON, PDF and DOCX files into the source-independent catalog. Originals are hashed and referenced by path, never copied, uploaded or modified. Text is searchable and page counts are retained; duplicate files are skipped, changed files keep revisions, extraction failures are explicit, and import history is recorded. PDF and DOCX text extraction use optional local packages; scanned PDFs without a text layer are reported rather than OCRed. See [Documents](docs/DOCUMENTS.md).

```sh
python3 dispatch.py documents preview ~/documents
python3 dispatch.py documents import ~/documents
```

**Local AI summaries** — generate message and conversation summaries with a locally running Ollama instance. Disabled by default; requires `ai.enabled` and `ai.backend=ollama` in preferences. Summaries are derived text, never evidence. See [AI summarization](docs/AI_SUMMARIZATION.md).

```sh
python3 dispatch.py summarize run HASH
python3 dispatch.py summarize run --all --type thread
```

**Unified search** — search archived email and imported records together;
snippets are excerpts of the stored text, never generated. The desktop search
adds source, exact sender/actor, record-kind, tag and date-range filters.
Totals are exact counts unless a tag filter is applied. Each source index is
streamed in rank order and merged lazily, so paging continues beyond the
former 5,000-candidate ceiling without loading the archive into memory. The
desktop runs searches as cancellable background jobs and reports incomplete
counts honestly. Malformed query
expressions are rejected with an explanation and syntax help instead of
silently returning no matches. The Advanced workspace builds nested boolean
groups over text, sender/actor, record kind, source, date and tag rules. Each
rule is evaluated as a set; NOT excludes its child from the selected sources,
so negation is exact rather than a filter on an already-ranked page. Text
rules use FTS5 syntax, tag rules apply to email only, and results are ranked by
summed text relevance then newest declared date with an exact total. Query
trees can be saved by name inside a research workspace and loaded or deleted
later; saving an existing name updates that query.

```sh
python3 dispatch.py search-all "receipt"
python3 dispatch.py search-all "bullion" --sources facebook
```

**Desktop application** — a Tauri 2 shell with a Vue 3 interface drives the
Python engine over the versioned IPC protocol. Workspaces include an Overview
dashboard (unique records, mailbox origins, undated counts, coverage, storage,
records by year); a paged timeline with oldest/newest ordering, sender filter,
date range and optional document inclusion; unified search with deep paging, date range and cancellation;
grounded research in the Intelligence workspace;
a nested boolean
query builder; Sources; a
background Import Center with preview, progress, cancellation and history;
Research; Collections, including adding the open message from the Timeline or
the open record from the Search reader; Journal with revision history; archive
Reports; Relationships; synchronization; Health with resumable repair jobs;
Backup with schema status and validated backup, verification and restore; and
Preferences. From a checkout of the development branch or v0.4.0-beta tag:

```sh
cd frontend && npm install
npm run tauri -- dev
```

Development runs the engine from the checkout. To build a distributable
app, first produce the standalone engine sidecar for the host, then package:

```sh
python3 scripts/build_engine.py
cd frontend && npm run tauri -- build --config src-tauri/tauri.bundle.conf.json
```

The shell prefers a bundled `hb-engine` binary, falls back to
`python3 dispatch.py` during development, and accepts `HB_ENGINE` /
`HB_ENGINE_SCRIPT` overrides. See [Packaging](docs/PACKAGING.md).

The Tkinter workstation (`dispatch gui`) remains available as a fallback for environments without the packaged shell.

## License and community

Copyright (c) 2026 Honey Badger Universe.

Current and future distributions of this source tree are licensed under GPL-3.0-only. Commercial use is permitted under the license, including its source-distribution and copyleft requirements. The project itself is a community-oriented FOSS undertaking, without paid support or service commitments. Prior distributions released under MIT retain their original license rights. See [LICENSE](LICENSE) for the complete terms.
