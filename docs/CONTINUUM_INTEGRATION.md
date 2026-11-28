# Optional Continuum integration

**Independent by design. Interoperable by choice. Intelligent when desired.**

HB Dispatch is a standalone email archive. HB Continuum includes its own email ingestion engine and does not require a separate Dispatch installation. Neither requires AI or cloud services.

To connect them safely, export or copy selected original EML files and import them into a separate Continuum archive. Keep a verified full backup. Importing EML does not carry mailbox provenance or research overlays. Do not share a writable database between different engine versions until compatibility is verified.

## Stable interchange manifest

`dispatch.py interchange DESTINATION [--since ISO] [--limit N]` writes a portable, read-only description of the archive for another Honey Badger application. Dispatch remains the only writer of its own archive; the manifest is a snapshot that the reader may store separately.

Format `hb-dispatch-interchange-1` is a single JSON object:

```json
{"format": "hb-dispatch-interchange-1",
 "messages": [
   {"sha256": "...", "subject": "...", "sender": "...", "date": "...", "sent_ts": 1704067200,
    "message_id": "...", "reply_to": "...", "recipient": "...", "cc": "...", "bcc": "...",
    "attachments": [{"filename": "rows.csv", "content_type": "text/csv", "size": 42, "sha256": "..."}],
    "origins": [{"account": "imap.example.invalid|you@example.invalid", "folder": "INBOX",
                 "validity": "1", "uid": "7", "first_seen": "2024-01-01 12:00:00"}]}]}
```

- `sha256` identifies the original message exactly and is the same value `export`, `verify` and `attachments` use.
- Message bodies are deliberately omitted. A reader that is authorised to read content resolves `sha256` against an exported EML file or the archive's `raw/` directory.
- `origins` is the provenance record: account, folder, UIDVALIDITY, UID and acquisition time.
- `--since` selects messages acquired at or after that timestamp for incremental hand-off; messages imported without mailbox provenance are excluded by that filter.
- `--limit` bounds a large export, and records are streamed so the writer's memory use stays flat.
- The destination file is created exclusively and is never overwritten.

Treat the manifest as data, not authority: Dispatch's archive remains the record of what was actually received.

The full [private intelligence workstation tutorial](https://github.com/James-HoneyBadger/HB_Continuum/blob/develop/continuum-integration/docs/PRIVATE_INTELLIGENCE_WORKSTATION.md) covers migration, local Ollama and optional ecosystem connections. It describes development-branch capabilities; check your installed version.

Local by default. Cloud by choice. Open by design. Owned by you.
