# HB Continuum

**Open-source, local-first personal knowledge archive and historical research workstation.**

HB Continuum is in active real-world use. It has moved beyond a proof of concept: live mailbox retrieval, searchable local preservation and source-backed historical research have been demonstrated with more than 31,000 unique archived messages across two mail providers. Development continues, but the core archival workflow is working software today.

## Independent and interoperable

**Independent by design. Interoperable by choice. Intelligent when desired.**

Each application works independently; optional integrations remain under user control. AI is never mandatory. See the [integration tutorial](docs/PRIVATE_INTELLIGENCE_WORKSTATION.md).

## Beyond email: a source-independent continuum

*Time is linear. Knowledge need not be.*

Part of the Honey Badger Universe, HB Continuum is designed around a broader vision than email archiving: preserve and explore historical information across otherwise disconnected sources, on infrastructure you control.

The existing email ingestion engine retains the name **Dispatch**. Future source adapters may support social media exports (including Facebook posts, comments and Messenger history), journals, documents, photographs and metadata, software development histories, and other structured or unstructured records.

The intended architecture preserves original source material and provenance, with source-specific ingestion and a unified searchable index. Cross-source timelines, genealogy, personal and organizational archives, historical research and evidence organization are potential applications. These additional importers and unified indexing are development goals, not implemented capabilities today.

### Second Me

An optional historical knowledge interface could help people rediscover their documented past using their own records and words. The goal is retrieval and evidence-backed reconstruction, not impersonation or invention. AI is optional and interchangeable; local models may enable offline analysis, while external AI services may receive selected records when explicitly authorized.

Local-first storage, open formats, user control, no mandatory cloud services, no telemetry, and no subscriptions remain foundational principles.

**The intelligence is replaceable. The memories are yours.**

## Demonstrated in real-world use

As of November 26, 2026, a live deployment had archived 31,441 unique messages across Gmail and IONOS, with matching SQLite message, origin, full-text index and original EML counts. SQLite quick integrity checks passed. A third provider, Apple iCloud Mail, subsequently began importing successfully. These checks do not establish complete mailbox coverage or content-level verification.

Practical investigations have included:

- Reconstructing consumer billing disputes, cancellation notices and correspondence timelines.
- Cross-referencing transaction confirmations against independently obtained financial records.
- Rebuilding a precious-metals purchase ledger from orders, shipment notices and cancellations.
- Exploring historical correspondence, recurring topics and account activity across providers.

These are actual research outcomes, not hypothetical feature claims. Some investigations used authorized external analysis of the local archive; HB Continuum itself supplies the searchable evidence foundation, not an automated financial or legal adviser. Private correspondence and underlying records are not published.

**Status:** the archival core is operational. The **v0.4.0-alpha** milestone builds on the [v0.3.0 release](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.3.0) with a source-independent record catalog for exported social archives, unified and nested boolean search across email and catalog records, a relationship explorer, collections, journal and report workflows, a Tauri 2 + Vue desktop shell, and verified backup and restore across all three databases. It is an alpha milestone tag, not a claim of comprehensive security certification.

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

Python 3.12+ with SQLite FTS5 and optional Tkinter.

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

For mailbox names containing spaces, use normal shell quoting, e.g. `--folder "Sent Items"` or `--folder "Sent Messages"`. HB Continuum quotes the IMAP mailbox internally and recognizes origins recorded by older versions with literal surrounding quotes.

Use `--archive PATH` before the subcommand to select storage. Sync uses TLS, read-only mailbox selection and BODY.PEEK. Passwords are prompted for, never stored by the application. Provider-specific authentication may be required. Gmail OAuth and a native MCP integration remain future work. Manual synchronization prompts for passwords; scheduled synchronization supports platform-specific schedulers and credential stores.

## Engine layout

The engine implementation lives in `hb_engine/`, with the CLI, IPC server, archive, catalog, research overlay, migrations and search modules sharing one package. `dispatch.py` remains the command-line and PyInstaller entry point, and the historical top-level module names are compatibility aliases, so existing scripts and tests keep the same imports. The archive layout, IPC protocol and sidecar contract are unchanged.

## Privacy and limitations

Original EML files are preserved by SHA-256 with SQLite search and mailbox provenance. Hashes detect changes, not authenticity or certified chain of custody. No telemetry or sending. HTML is not rendered. Use an encrypted disk and keep all real mail and credentials outside the repository. Verify backup and restore with `dispatch backup`, `dispatch verify-backup` and `dispatch restore`, and diagnose local consistency with `dispatch health` (see [Archive hardening](docs/ARCHIVE_HARDENING.md)). Failed imports may leave unindexed raw files; `dispatch recover-orphans` and `dispatch reindex` repair them from the preserved originals. Failed exports may be partial. Live IMAP retrieval has been demonstrated with IONOS, Gmail and iCloud Mail; comprehensive GUI, provider compatibility, hostile-MIME and restoration testing remain ongoing. Search indexes plain-text bodies, HTML reduced to offline text, and attachment names, types and bounded text; PDF, Office and image contents are not converted. Exact-byte deduplication does not guarantee semantic deduplication across providers. Do not use HB Continuum as the sole evidence archive.

## Scheduled synchronization

Maintain multiple mailboxes automatically with the local synchronization center, configurable interval or daily schedules and platform-specific credential stores. See [Scheduled synchronization](docs/SCHEDULED_SYNC.md). Finish any older manual import before enabling the service.

## Configuration center

Customize the workstation per archive with validated, portable settings for appearance, research, file locations, integrity checks and synchronization. Open **Configuration center** in the desktop application. See [Configuration reference](docs/CONFIGURATION.md).

## Research workbench

Create workspaces, saved queries, classification rules, tags, custom metadata and reusable CSV reports without changing original correspondence. See [Research workbench](docs/RESEARCH.md).

## Import center, history and source manager

Desktop imports run as cancellable background jobs with real progress. Every EML, IMAP and Facebook import appends a run to the archive's import history, recording what was examined, what was new, what already existed and what failed. A killed process is reported as interrupted rather than rewritten as success.

The Sources workspace derives coverage from stored provenance: unique messages and mailbox occurrences per account, folders read, normalized date coverage, last import status, catalog sources and storage footprint. It states explicitly that importing folders never proves an account is complete. Importing `.eml` files preserves messages without inventing an account.

Each account or catalog source can be verified independently: email checks are scoped to that account's messages, and catalog verification re-hashes the recorded export files where they still exist. Verification runs in the background with progress, cancellation and explicit altered/missing counts.

Sources can be disabled — stopping new automatic imports while every historical record stays searchable — and re-enabled. Removal is preview-first: HB Continuum counts the unique messages, shared duplicates and raw bytes involved and explains what will be kept before anything is deleted. Messages shared with another account, and messages imported from `.eml` files, are never removed by an account removal. Removing a catalog source deletes its catalog records, not the original export files. See [Migration and compatibility](docs/MIGRATION.md) for the schemas and audit log.

## Evidence collections

Group selected records into named collections inside a research workspace. Items are references to preserved records — SHA-256 hashes for email, record ids for catalog entries — with optional notes. Nothing is copied into the research overlay, and deleting a collection never deletes an archived record. A referenced record that disappears stays listed and is marked missing. Collections export as Markdown or JSON evidence manifests with stable identifiers, notes and explicit limitations, and never replace an existing file. Selected search results can be added to a collection directly from the Search workspace.

A collection can also hold **report drafts**: titled notes that render a chronology ordered by declared date, evidence gaps for records that have gone missing, and explicit limitations. Drafts export as Markdown, JSON or standalone HTML, are stored as user annotations rather than evidence, and never replace an existing file.

## Relationship explorer

The Relationships workspace links participants only when they appear together in the same archived email thread (Message-ID / In-Reply-To) or the same catalog conversation. It never infers a relationship from a shared subject, a similar date or an address-book match. Email addresses and catalog actor names stay separate identities, each edge lists the shared threads, message counts and example records, and 12 participants per thread, 100 nodes and 500 edges are hard caps with explicit truncation. A shared thread is co-participation, not proof of any personal or causal connection.

## Journal and archive reports

The Journal stores your own retrospective entries in the research overlay, separate from preserved evidence. Every edit adds a revision; saving without changes adds nothing. Removal is soft, so history stays inspectable and the entry can be restored.

The Reports workspace writes a self-contained Markdown, JSON or standalone HTML archive report: summary, date coverage, records by year, email accounts, catalog sources, consistency checks, recent imports and explicit limitations. Reports are written outside the archive, never replace an existing file, and state that stored counts and hash checks are not remote truth or legal certification.

## Performance baseline

`scripts/benchmark.py` builds deterministic synthetic archives and measures ingest, search, timeline paging, dashboard and peak memory. Current baselines and reproduction steps are in [Benchmarks](docs/BENCHMARKS.md). The harness never touches a real archive and refuses a non-empty work directory.

## Beyond email (new)

HB Continuum is growing from an email archive into a source-independent historical record. These capabilities are opt-in and still evolving.

**Facebook import** — import posts, comments, group posts, messages, events, photos/videos, and reactions from a user-obtained Facebook JSON export. Post/comment update timestamps and revision versions are preserved, and message/post attachment metadata is stored and searchable without copying media files. Original exports are never uploaded or modified. See [Facebook import](docs/FACEBOOK_IMPORT.md).

```sh
python3 dispatch.py facebook preview ~/facebook-export
python3 dispatch.py facebook import ~/facebook-export
python3 dispatch.py facebook search "receipt"
python3 dispatch.py facebook list --kind event
```

**Local AI summaries** — generate message and conversation summaries with a locally running Ollama instance. Disabled by default; requires `ai.enabled` and `ai.backend=ollama` in preferences. Summaries are derived text, never evidence. See [AI summarization](docs/AI_SUMMARIZATION.md).

```sh
python3 dispatch.py summarize run HASH
python3 dispatch.py summarize run --all --type thread
```

**Unified search** — search archived email and imported records together;
snippets are excerpts of the stored text, never generated. The desktop search
adds source, exact sender/actor, record-kind, tag and date-range filters.
Totals are exact counts unless a tag filter is applied, and a listing limit is
reported explicitly rather than disguised as a total. Malformed query
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
records by year); a paged timeline with oldest/newest ordering, sender filter
and date range; unified search with paging and date range; a nested boolean
query builder; Sources; a
background Import Center with preview, progress, cancellation and history;
Research; Journal with revision history; archive Reports; synchronization;
Health with resumable repair jobs; Backup with schema status and validated
backup, verification and restore; and Preferences. From a checkout:

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

The Tkinter workstation (`dispatch gui`) remains the stable fallback until
the new shell reaches functional parity.

## License and community

Copyright (c) 2026 Honey Badger Universe.

Current and future distributions of this source tree are licensed under GPL-3.0-only. Commercial use is permitted under the license, including its source-distribution and copyleft requirements. The project itself is a community-oriented FOSS undertaking, without paid support or service commitments. Prior distributions released under MIT retain their original license rights. See [LICENSE](LICENSE) for the complete terms.
