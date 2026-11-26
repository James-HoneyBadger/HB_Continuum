# Facebook import

HB Continuum imports **user-obtained** Facebook JSON exports. It never
scrapes Facebook, never requires account credentials, and never uploads any
imported material. The source is an export the user has already downloaded
from Facebook's "Download Your Information" feature.

## What is imported

The importer recognizes six categories today:

- **Posts** — `your_posts_*.json`, `posts.json`, and group posts via
  `your_posts_in_groups.json` / `group_posts.json`.
- **Comments** — `comments.json` and `your_comments_in_groups.json`.
- **Messages** — `messages/inbox/<conversation>/message_*.json`.
- **Events** — `your_events.json` / `events.json` (name, description, and
  `start_timestamp`).
- **Photos/videos** — `your_videos.json`, `your_photos.json`, and
  `photos_and_videos/*.json` (title, description, `creation_timestamp`).
- **Reactions** — `likes_and_reactions/*.json` (reaction type and actor).

Each record is stored in the source-independent catalog
(`catalog.sqlite3`) with:

- `source_type` = `facebook`.
- `source_key` — the conversation title for messages, or the export list
  key for posts/comments (so group posts and timeline posts stay distinct).
- `record_kind` — `post`, `comment`, or `message`.
- `actor` — the sender for messages; posts/comments are the account owner
  and have no actor.
- `occurred_at` and `occurred_precision` — normalized UTC timestamp and
  `second`, `ms`, or `unknown`.
- `body` — extracted text.
- `original_json` — the original record object, preserved verbatim.

## Provenance

The original export files are **not** copied or modified. The catalog
records each source file's SHA-256, path, size, and import time in
`source_files`, and every record keeps its original JSON. A record is
addressable by `sha256(source_key + canonical JSON)`.

## Commands

```sh
python3 dispatch.py --archive ~/HB_Continuum facebook preview ~/facebook-export
python3 dispatch.py --archive ~/HB_Continuum facebook import ~/facebook-export
python3 dispatch.py --archive ~/HB_Continuum facebook search "receipt"
python3 dispatch.py --archive ~/HB_Continuum facebook list --kind event --limit 50
```

`preview` reports files discovered, recognized categories, estimated record
counts, and unsupported files. `import` is idempotent: re-running it skips
files already imported (matched by SHA-256), so interrupted imports resume
safely and overlapping exports are deduplicated per record. `search` runs a
full-text query over imported record text; `list` browses records filtered
by `--kind` and `--actor`.

## Counting semantics

- `files_discovered` — JSON files found after expanding directories (hidden
  files are skipped).
- `files_imported` — files whose records were committed in this run.
- `files_skipped` — files whose SHA-256 was already in the catalog.
- `files_unsupported` — files of a recognized-but-unimplemented category
  (e.g. events, media, reactions). These are not recorded, so a future
  importer can process them.
- `records_encountered` — candidate record objects found in supported files.
- `records_imported` — new records inserted.
- `records_duplicate` — records already present (overlapping exports).
- `records_unsupported` — items in supported files that could not be
  normalized (e.g. non-object entries).
- `parse_errors` — files that failed JSON/UTF-8 parsing.

## Limitations

- Only posts, comments, messages, events, photos/videos, and reactions are
  imported. Post/comment revision entries and some newer reaction layouts
  are detected as records where the shape matches; unrecognized shapes are
  reported as unsupported.
- Whole JSON files are parsed into memory; very large single files (many
  hundreds of MB) may be slow or memory-heavy.
- Timestamps are taken as declared by the export; they are not verified
  against any external clock.
- Encoding repairs are not attempted silently. A file that is not valid
  UTF-8/JSON is reported as a parse error and left untouched.
