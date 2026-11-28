# HB Continuum

**A local-first personal archive and historical research application.**

HB Continuum is an independent, open-source hobby project within the Honey Badger Universe. Originally developed as HB Dispatch to preserve email correspondence, it now supports other historical records, searchable documents, research tools and optional local AI.

Its purpose is straightforward: help people preserve and explore their documented history on infrastructure they control.

**Current release: [v0.5.0-beta](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.5.0-beta)** — a source-only beta, primarily developed and qualified for Apple Silicon macOS.

[Release notes and source download](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.5.0-beta) · [Full user and developer README](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/README.md) · [Active development branch](https://github.com/James-HoneyBadger/HB_Continuum/tree/develop/intelligence-update)

**Branch note:** The default `main` branch retains the earlier Dispatch-era code baseline. Use the release tag for the capabilities described here.

## What Continuum does

| Capability | v0.5 beta |
| --- | --- |
| Email preservation | Read-only IMAP, original EML storage, SHA-256 verification, mailbox provenance and scheduled synchronization |
| Social history | Import user-obtained Facebook JSON exports |
| Document research | Local text, Markdown, CSV, JSON, PDF and DOCX ingestion; optional PDF/DOCX attachment extraction |
| Search | Unified full-text search, deep pagination beyond the former 5,000-candidate ceiling, filters and nested Boolean queries |
| Historical research | Timelines, participant relationships, collections, journals, saved searches and reports |
| Optional local AI | Ollama-based research conversations with bounded evidence and inspectable source references |
| Database protection | Optional SQLCipher encryption, explicit migration, archive lock/unlock and encrypted database backups |
| Desktop | Tauri/Vue application with archive selection, import progress, record navigation, health checks and recovery |

No telemetry, advertising, mandatory accounts, subscriptions or cloud inference. AI is disabled by default, and the archive remains useful without it.

## Security and privacy — please read

Continuum can contain sensitive personal information. Protecting that information is a central development priority.

- Optional SQLCipher encrypts the archive, catalog and research databases. New encrypted archives currently require the optional `sqlcipher3` package and CLI creation; new archives created through the desktop are plaintext.
- Existing plaintext archives are never migrated automatically. Explicit migration creates a separate encrypted destination and preserves the original.
- Encrypted database backups retain database encryption, and scheduled synchronization defers while an encrypted archive is locked.
- Raw EML files, configuration, external documents and exports are outside the database encryption boundary. Use encrypted storage for the entire archive and backups, such as an encrypted APFS volume or disk image on macOS.
- Encryption at rest does not protect an unlocked archive against every form of host compromise. Keep independent backups and test restoration before relying on the archive.

Read [Encryption](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/ENCRYPTION.md), [Encryption migration](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/ENCRYPTION_MIGRATION.md) and the [Security threat model](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/SECURITY_MODEL.md) before storing sensitive information.

## Getting started

Use the released source rather than the older default branch:

```sh
git clone --branch v0.5.0-beta https://github.com/James-HoneyBadger/HB_Continuum.git
cd HB_Continuum
python3 dispatch.py --version
python3 dispatch.py --help
```

Requires Python 3.12+ with SQLite FTS5. Building the desktop also requires Node.js 22+, Rust and Tauri platform prerequisites.

```sh
cd frontend
npm ci
npm run tauri -- dev
```

Start with a separate test archive and fictional records. For encrypted archive setup, install the documented SQLCipher dependency and follow the encryption guide. The beta does not include signed or notarized installers.

## Documentation

- [Practical tutorial](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/TUTORIAL.md)
- [Full release README and CLI reference](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/README.md)
- [Document ingestion](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/DOCUMENTS.md)
- [Facebook import](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/FACEBOOK_IMPORT.md)
- [Intelligence workspace](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/INTELLIGENCE.md)
- [Archive hardening and recovery](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/ARCHIVE_HARDENING.md)
- [Packaging](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/PACKAGING.md)
- [Implementation and qualification status](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/docs/engineering/IMPLEMENTATION_STATUS.md)

## Beta status and limitations

The published v0.5 qualification reports 357 Python tests with no failures (355 passed and two skipped with SQLCipher), successful static analysis, frontend and Rust builds, native Apple Silicon macOS bundle and engine smoke tests, and 12 successful CI jobs. See the [release notes](https://github.com/James-HoneyBadger/HB_Continuum/releases/tag/v0.5.0-beta) for the precise scope.

This is not a comprehensive security audit. Packaged Linux and Windows desktop applications are not qualified. Live Ollama inference and full interactive desktop acceptance have not been established by the release qualification. Retrieval is keyword-based, not semantic; model answers are interpretations, not evidence, and a valid citation does not establish factual correctness. Scanned PDFs are not OCRed. Read-only IMAP does not delete server mail, and hashes do not establish authenticity or certified chain of custody.

## Development direction

Continuum is maintained primarily by one developer. Development is incremental, guided by actual use rather than a fixed feature schedule.

The priorities are reliable preservation and recovery, protection of sensitive records, straightforward research and search, optional local AI, and a maintainable desktop experience. Future improvements will be selected in small, independently testable milestones. There are no delivery-date commitments, commercial support obligations or promises of comprehensive platform support.

The idea of exploring one's documented past through local intelligence is an inspiration, not a commitment to build an artificial replica of a person.

Constructive feedback and contributions are welcome.

*The intelligence is replaceable. The memories are yours.*

## License

Copyright (c) 2026 Honey Badger Universe. [GPL-3.0-only](https://github.com/James-HoneyBadger/HB_Continuum/blob/v0.5.0-beta/LICENSE). Commercial use is permitted under the license, subject to its applicable source-distribution and copyleft requirements. Earlier MIT-licensed distributions retain their original license rights.
