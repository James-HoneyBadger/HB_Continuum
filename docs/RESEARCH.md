# Research workbench

Open **Research workbench** from the desktop correspondence workstation.
Research overlays reside in research.sqlite3 alongside archive.sqlite3.
They never rewrite original EML files or the archive's message metadata.
Back up both databases and the raw directory while writes are stopped.

- Workspaces organize named saved searches.
- Saved searches accept SQLite FTS expressions, optional required tags,
  and a configurable result limit (1–50,000). Empty queries select all
  messages up to the limit. Invalid expressions report an error.
- Rules match subject, sender, plain-text body or declared date using
  case-insensitive contains, equals or starts-with matching.
  Rules assign tags; Rebuild rule tags explicitly recalculates them.
  Manual tags remain separate and are retained on rule rebuild.
- Select messages in the main workstation before applying manual tags or
  field values. Custom fields support text, finite numbers, ISO dates,
  Boolean values and enumerated choices. A populated definition cannot
  be changed incompatibly.
- Reports select an existing saved search, choose columns, and optionally
  group by sender, declared year or tag. Group totals reflect the saved
  search limit; tag counts overlap when messages have multiple tags.
  Preview displays results; CSV export creates a new file and protects
  spreadsheet formula-like text. It is not a raw evidence export.

Example: create a Metals workspace, save a rule matching sender
jmbullion.com and assigning Bullion, rebuild rule tags, then save a
search requiring Bullion. Create a report using that search grouped by
year, or export selected message headers.

This initial workbench uses explicit rule rebuilds, not automatic
classification on every import. Search and rebuild operations may take
time on large archives. Custom field filtering, richer visual reports,
scheduled backup/verification and full profile portability are future
development items. Do not publish research databases or exports without
reviewing their private contents.
