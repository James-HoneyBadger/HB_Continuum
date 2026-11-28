# Preferences (configuration reference)

HB Continuum exposes archive-specific preferences through the desktop
application's **Preferences** workspace. No source code editing is required.
The legacy Tk workstation still exposes the older configuration center, but
the native Tauri shell is the primary interface. Save changes and restart the
workstation to apply appearance settings. Source-visibility changes apply to
the next search or timeline load. Synchronization reads current preferences at
the beginning of each folder run.

| Area | Options |
|---|---|
| Appearance | System/light/dark theme, reader font family and size, wrapping, horizontal or vertical message panes, initial window dimensions, subject and sender column widths, message IDs and SHA-256 visibility in the individual message reader |
| Research | Search, recent, timeline and correspondent result limits (10–5000), FTS or exact phrase search, startup recent view or saved query, and hiding disabled sources from unified search, the timeline and correspondent counts |
| Files | Default EML import and evidence export directories |
| Integrity | Optional hash verification at startup |
| Synchronization | Network timeout (10–300 seconds), per-folder batch cap (0 means unlimited) |

Account schedules, mailbox selections, credentials and pause/resume controls
are in the separate **Synchronization center**. See [Scheduled sync](SCHEDULED_SYNC.md).

Preferences live in the private archive directory in a versioned JSON file.
Export/import transfers only preferences, not emails, account profiles or
passwords. Exported preferences can still reveal local paths or search terms;
review before sharing. Import previews settings in the editor; click Save
to apply. Restore defaults likewise requires Save.

Hiding disabled sources affects default views only: unified search, the
timeline and correspondent counts. The Sources inventory, archive-wide
dashboard and explicit advanced queries still show the historical records,
and nothing is deleted or re-enabled automatically.

Hash verification on startup may take considerable time for large archives.
A nonzero batch cap deliberately limits each sync; subsequent runs resume
from the remaining unseen UIDs. A successful capped run does not mean the
entire mailbox is current.

Read-only IMAP, exact-byte preservation, hash verification on ingest,
deduplication and source tracking are core safeguards, not optional
preferences. No configuration can enable server-side deletion or sending.
