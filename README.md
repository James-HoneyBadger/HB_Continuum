# HB_Dispatch

Experimental local-first email archive and evidence research workstation. Early-stage release — read the limitations below.

## Your mail. Your archive. Your choice.

**Your email provider should be your communications service, not the permanent custodian of your correspondence.**

HB Dispatch is built around personal digital sovereignty: keep your own searchable, locally controlled copy of your email history, independent of any hosting provider, subscription tier or cloud archive. Changing providers should not mean leaving years of correspondence behind.

The intended workflow is simple: retrieve messages, preserve their original EML data, index them locally, verify their integrity, and maintain independent backups. Once archival and recovery have been verified, you can manage server storage separately from your long-term retention needs.

- Your correspondence, stored on hardware you control.
- Your search index, without a mandatory cloud service.
- Your retention decisions, rather than a provider's storage quota.
- Your backups, independent of the mailbox host.

HB Dispatch is free and open-source software. No telemetry, advertising, mandatory online account or subscription. It complements existing mail clients rather than requiring you to replace them.

**Important:** the current implementation is experimental and uses read-only IMAP retrieval; it does not automatically delete server mail. Verified restoration, comprehensive multi-account management and safe retention workflows are development goals, not finished features. Keep independent backups and do not remove server copies solely on the strength of this experimental archive.

## Learn by doing

**[Read the complete practical tutorial](docs/TUTORIAL.md).** Start with a fictional email, learn how the archive works, connect multiple providers, reconstruct historical correspondence, and build an independent backup routine. The guide distinguishes current capabilities from alpha and planned features.

## A practical use case

**[From scattered inboxes to a personal historical intelligence archive](docs/USE_CASE_PERSONAL_HISTORY.md).** Follow a fictional user who combines years of correspondence across multiple providers, reconstructs forgotten events, prepares source-backed reports and explores an optional personal knowledge assistant. The scenario separates current archival capabilities from external analysis and future integrations.

## Quick start

Python 3.12+ with SQLite FTS5 and optional Tkinter.

```sh
python3 dispatch.py import sample.eml
python3 dispatch.py search invoice
python3 dispatch.py verify
python3 dispatch.py gui
python3 dispatch.py sync imap.example.invalid user@example.invalid --folder INBOX
python3 dispatch.py export evidence HASH
python3 -m unittest discover -s tests -v
```

Use `--archive PATH` before the subcommand to select storage. Sync uses TLS, read-only mailbox selection and BODY.PEEK. Passwords are prompted for, never stored by the application. Provider-specific authentication may be required. Gmail OAuth, Keychain and MCP are future work.

## Privacy and limitations

Original EML files are preserved by SHA-256 with SQLite search and mailbox provenance. Hashes detect changes, not authenticity or certified chain of custody. No telemetry or sending. HTML is not rendered. Use an encrypted disk and keep all real mail and credentials outside the repository. Back up the entire archive with the app closed. Failed imports may leave unindexed raw files; failed exports may be partial. Live IMAP and GUI are unverified. Resource limits, atomic exports, attachment and thread UI, and broader hostile-MIME hardening remain future work. Do not use as the sole evidence archive or for untrusted bulk imports yet.
