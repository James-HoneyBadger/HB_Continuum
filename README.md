# HB_Dispatch

**Operational local-first email archive and personal historical research workstation.**

HB Dispatch is in active real-world use. It has moved beyond a proof of concept: live mailbox retrieval, searchable local preservation and source-backed historical research have been demonstrated with more than 20,000 unique archived messages across two mail providers. Development continues, but the core archival workflow is working software today.

## Demonstrated in real-world use

As of November 26, 2026, a live deployment had indexed 20,185 unique messages, with a second mailbox import still underway. The SQLite message count and full-text index count reconciled at that snapshot. An earlier completed 12,798-message import also passed SQLite integrity checks and reconciled against its original EML file count.

Practical investigations have included:

- Reconstructing consumer billing disputes, cancellation notices and correspondence timelines.
- Cross-referencing transaction confirmations against independently obtained financial records.
- Rebuilding a precious-metals purchase ledger from orders, shipment notices and cancellations.
- Exploring historical correspondence, recurring topics and account activity across providers.

These are actual research outcomes, not hypothetical feature claims. Some investigations used authorized external analysis of the local archive; HB Dispatch itself supplies the searchable evidence foundation, not an automated financial or legal adviser. Private correspondence and underlying records are not published.

**Status:** the core archive is operational and published as the [v0.3.0 release](https://github.com/James-HoneyBadger/HB_Dispatch/releases/tag/v0.3.0), which adds local scheduled synchronization, a configuration center and a research workbench to the archival core. The release is a milestone tag, not a claim of comprehensive security certification.

## Your mail. Your archive. Your choice.

**Your email provider should be your communications service, not the permanent custodian of your correspondence.**

HB Dispatch is built around personal digital sovereignty: keep your own searchable, locally controlled copy of your email history, independent of any hosting provider, subscription tier or cloud archive. Changing providers should not mean leaving years of correspondence behind.

The working archival workflow is simple: retrieve messages, preserve their original EML data, index them locally, verify their integrity, and maintain independent backups. Once archival and recovery have been verified, you can manage server storage separately from your long-term retention needs.

- Your correspondence, stored on hardware you control.
- Your search index, without a mandatory cloud service.
- Your retention decisions, rather than a provider's storage quota.
- Your backups, independent of the mailbox host.

HB Dispatch is free and open-source software. No telemetry, advertising, mandatory online account or subscription. It complements existing mail clients rather than requiring you to replace them.

**Important:** HB Dispatch uses read-only IMAP retrieval and does not delete server mail. Keep independent backups and test restoration before removing any server copies. Comprehensive mailbox coverage and restoration testing remain essential; a successful import alone does not establish completeness.

## Learn by doing

**[Read the complete practical tutorial](docs/TUTORIAL.md).** Start with a fictional email, learn how the archive works, connect multiple providers, reconstruct historical correspondence, and build an independent backup routine. The guide distinguishes working capabilities from planned enhancements.

## A practical use case

**[From scattered inboxes to a personal historical intelligence archive](docs/USE_CASE_PERSONAL_HISTORY.md).** Follow a fictional user who combines years of correspondence across multiple providers, reconstructs forgotten events, prepares source-backed reports and explores an optional personal knowledge assistant. The scenario separates current archival capabilities from external analysis and future integrations.

## Quick start

Python 3.12+ with SQLite FTS5 and optional Tkinter.

```sh
python3 dispatch.py --version
python3 dispatch.py import sample.eml
python3 dispatch.py search invoice
python3 dispatch.py verify
python3 dispatch.py gui
python3 dispatch.py sync imap.example.invalid user@example.invalid --folder INBOX
python3 dispatch.py export evidence HASH
python3 -m unittest discover -s tests -v
```

Use `--archive PATH` before the subcommand to select storage. Sync uses TLS, read-only mailbox selection and BODY.PEEK. Passwords are prompted for, never stored by the application. Provider-specific authentication may be required. Gmail OAuth and a native MCP integration remain future work. Manual synchronization prompts for passwords; scheduled synchronization is macOS-only and reads credentials from the login Keychain.

## Privacy and limitations

Original EML files are preserved by SHA-256 with SQLite search and mailbox provenance. Hashes detect changes, not authenticity or certified chain of custody. No telemetry or sending. HTML is not rendered. Use an encrypted disk and keep all real mail and credentials outside the repository. Back up the entire archive with the app closed. Failed imports may leave unindexed raw files; failed exports may be partial. Live IMAP retrieval has been demonstrated with IONOS and Gmail; comprehensive GUI, provider compatibility, hostile-MIME and restoration testing remain ongoing. Search currently indexes plain-text message content rather than all HTML or attachments. Exact-byte deduplication does not guarantee semantic deduplication across providers. Do not use HB Dispatch as the sole evidence archive.

## Scheduled synchronization (macOS)

Maintain multiple mailboxes automatically with the local synchronization center, configurable interval or daily schedules, macOS Keychain credentials and a per-user LaunchAgent. See [Scheduled synchronization](docs/SCHEDULED_SYNC.md). Finish any older manual import before enabling the service.

## Configuration center

Customize the workstation per archive with validated, portable settings for appearance, research, file locations, integrity checks and synchronization. Open **Configuration center** in the desktop application. See [Configuration reference](docs/CONFIGURATION.md).

## Research workbench

Create workspaces, saved queries, classification rules, tags, custom metadata and reusable CSV reports without changing original correspondence. See [Research workbench](docs/RESEARCH.md).
