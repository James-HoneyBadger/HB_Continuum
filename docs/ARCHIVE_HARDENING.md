# Archive hardening and recovery

## New tools

Run these against an archive after stopping older sync processes. Back up
before upgrading. Use a separate destination on encrypted storage.

```sh
python3 dispatch.py --archive ~/HB_Mail_Archive health
python3 dispatch.py --archive ~/HB_Mail_Archive recover-orphans
python3 dispatch.py --archive ~/HB_Mail_Archive reindex
python3 dispatch.py --archive ~/HB_Mail_Archive backup /path/to/new-snapshot
python3 dispatch.py verify-backup /path/to/new-snapshot
python3 dispatch.py --archive /path/to/new-restored-archive restore /path/to/new-snapshot
```

- Health checks SQLite, foreign keys, search-index membership and duplicate
  index rows, raw-file coverage and SHA-256. A discrepancy returns a
  nonzero exit code. Counts alone are not a completeness check against IMAP.
- Orphan recovery reimports intact hash-named EML files without inventing
  provenance. A subsequent sync can supply the original mailbox origin.
  Invalid or oversized files are retained for investigation.
- Reindex upgrades existing messages from the preserved raw originals,
  checks their hashes, and commits per message. It resumes after interruption.
  It changes derived text, not original bytes or origin records.
- HTML-only messages are searchable as offline plain text. Scripts, styles
  and markup are not rendered or executed. Attachment filenames, MIME types
  and bounded text content are searchable; PDF/Office/image contents are
  not extracted yet. MIME processing remains subject to resource limits.
- Backups contain SQLite snapshots, indexed EML files, research overlays
  and archive configuration. They include SHA-256 manifests, integrity
  checks, foreign key checks and index coverage checks. Unindexed raw
  files are not included: run health and resolve orphans first.
- Restoration validates a snapshot and copies to a new destination;
  existing archives are never overwritten. Restored schedule profiles are
  disabled. Keychain credentials are not copied. Backups are not encrypted
  by the application; use an encrypted destination.
- Stop all archive and research/configuration writers before taking a
  consistent full-system backup. POSIX cooperative locks prevent new
  manual/scheduled imports from overlapping backup/reindex/recovery, but
  do not coordinate old executables, research overlays or arbitrary tools.
- A crash during final publication may leave a partial destination.
  Verify any backup before relying on it. Never delete the source solely
  because a backup command completed.

## Remaining boundaries

No authenticity certification, legal hold, immutable audit storage,
multi-user authorization, malware sandbox, comprehensive hostile-MIME
hardening, or enterprise compliance certification is claimed. The local
archive is not an independent forensic chain of custody. Full recovery
drills, provider compatibility, GUI testing and cross-platform CI remain
part of release validation.
