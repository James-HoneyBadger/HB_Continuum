# HB Continuum

**Open-source, local-first personal knowledge archive and historical research workstation.**

*Time is linear. Knowledge need not be.*

Part of the Honey Badger Universe, HB Continuum began as HB Dispatch, an email preservation engine, and has evolved into a broader workstation for preserving, organizing and exploring your documented history on infrastructure you control.

> **Current milestone: [v0.4.0-beta](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.4.0-beta)** — source-only beta.
>
> [Download the release](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.4.0-beta) · [Current development source and full README](https://github.com/James-HoneyBadger/HB_Continuum/tree/develop/continuum-integration) · [Release history](https://github.com/James-HoneyBadger/HB_Continuum/releases)

**Source branch note:** The current Continuum implementation is on `develop/continuum-integration` and the `v0.4.0-beta` tag. This `main` branch retains the earlier Dispatch-era code baseline; the capabilities below refer to the v0.4 beta.

## Your history. Your archive. Your choice.

**Independent by design. Interoperable by choice. Intelligent when desired.**

Local-first storage, open formats, user ownership, no telemetry, no advertising, no tracking, no mandatory accounts, subscriptions, cloud services or AI. Original evidence, annotations and generated interpretations remain distinct.

## What v0.4 delivers

| Capability | Current beta functionality |
| --- | --- |
| Email | Read-only IMAP, original EML preservation, SHA-256 verification, deduplication and provenance |
| Social history | Facebook JSON export ingestion, including posts, comments, messages, events, media metadata and reactions |
| Discovery | SQLite FTS5, unified search, nested Boolean queries, saved searches and filters |
| Historical exploration | Paged timelines, participant relationships and source management |
| Research | Workspaces, tags, evidence collections, report drafts, revision-tracked journal and archive reports |
| Maintenance | Scheduled synchronization, integrity checks, index repair, validated backups and restoration |
| Local intelligence | Optional Ollama message and conversation summaries |
| Desktop | Tauri 2 / Vue 3 interface with Python engine and legacy Tkinter fallback |

A deployment on November 26, 2026 preserved 31,441 unique messages across Gmail and IONOS, with reconciled storage and index counts and successful SQLite quick integrity checks. iCloud Mail ingestion subsequently began successfully. These observations do not establish complete mailbox coverage. Private source records are not published.

## Getting started

Use the published beta source, rather than assuming this branch contains the latest implementation:

```sh
git clone --branch v0.4.0-beta https://github.com/James-HoneyBadger/HB_Continuum.git
cd HB_Continuum
python3 dispatch.py --version
python3 dispatch.py --help
python3 -m unittest discover -s tests -v
```

Requires Python 3.12+ with SQLite FTS5. Desktop development additionally requires Node.js 22+, Rust and Tauri platform prerequisites.

```sh
cd frontend
npm install
npm run tauri -- dev
```

The beta is distributed as source, without signed application binaries. Start with fictional data in a separate test archive and follow the tutorial before connecting a real mailbox.

## Documentation

- [Full current README and CLI reference](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/README.md)
- [Practical tutorial](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/TUTORIAL.md)
- [Historical research use case](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/USE_CASE_PERSONAL_HISTORY.md)
- [Private intelligence workstation and optional integrations](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/PRIVATE_INTELLIGENCE_WORKSTATION.md)
- [Facebook import](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/FACEBOOK_IMPORT.md)
- [Archive hardening and recovery](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/ARCHIVE_HARDENING.md)
- [Local AI summarization](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/AI_SUMMARIZATION.md)
- [Packaging](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.4.0-beta/docs/PACKAGING.md)
- [Implementation and qualification status](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/engineering/IMPLEMENTATION_STATUS.md)
- [Performance benchmarks](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/BENCHMARKS.md)

## Beta qualification and limitations

The recorded v0.4 beta qualification includes 280 Python tests (278 passed, two skipped), successful static analysis, frontend build, Rust checks and tests, engine-sidecar smoke tests and a Tauri debug build. See the qualification record for scope. This is not a comprehensive security audit or a guarantee of complete interactive desktop validation.

Unified search currently pages over at most 5,000 fused candidates. Application-level encryption at rest and OAuth are not implemented. PDF, Office and image attachment content extraction remains limited. Facebook media bytes are not copied. Local AI currently summarizes messages and conversations rather than answering arbitrary questions across the entire archive.

Use encrypted storage, independent backups and tested restoration. Read-only IMAP does not delete server mail. Archive hashes detect changes, not authenticity or legal chain of custody. Do not use Continuum as your only evidence archive.

## The road ahead: historical intelligence

The proposed v0.5 **Intelligence Update** focuses on scalable retrieval, evidence-grounded conversational research through local Ollama, inspectable source references, additional document ingestion and optional Honey Badger interchange.

The longer-term **Second Me** vision is a historically grounded interface to your documented experiences, interests and projects. Its purpose is retrieval and reflection, not impersonation, invention or claims of consciousness.

These are planned capabilities, not features of the current beta.

**The intelligence is replaceable. The memories are yours.**

## License and community

Copyright (c) 2026 Honey Badger Universe.

HB Continuum is a community-oriented FOSS project licensed under [GPL-3.0-only](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/LICENSE). Commercial use is permitted subject to the license, including applicable source-distribution and copyleft obligations. Earlier MIT-licensed distributions retain their original license rights. There is no paid support or service commitment.
