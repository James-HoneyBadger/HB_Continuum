# ADR-003: Desktop IPC protocol

- **Status:** Accepted (implemented in `ipc.py`)
- **Date:** 2026-11-26

## Context

The modern desktop shell needs a controlled way to drive the Python engine.
The directive requires a narrowly scoped, versioned IPC protocol and forbids
a general-purpose local HTTP API without a documented security design.

## Decision

Use a **newline-delimited JSON protocol over the engine's stdin/stdout**,
spawned as `python3 dispatch.py --archive <root> serve`.

- Every request carries `protocol_version`, `request_id`, `method`, and
  `params`.
- Every response carries the same `protocol_version` and `request_id`, with
  either `result` or `error: {code, message}`.
- Long-running jobs emit `event` objects (`progress`, `job_complete`,
  `job_error`) tagged with a `job_id`.
- Methods are an explicit allowlist: `ping`, `stats`, `search`, `message`,
  `thread`, `record`, `verify`, `health`, `migrate_status`, `reindex`,
  `recover_orphans`, `backup`, `verify_backup`, `restore`, `import_eml`,
  `preferences`, `preferences_set`, the `research_*` overlay methods,
  `export_evidence`, the `schedule_*` methods, `summarize`, `cancel` and
  `shutdown`.
- `health` inspects an existing archive through a read-only connection and
  never migrates or writes during the request, returning
  `ARCHIVE_NOT_AVAILABLE` or `ARCHIVE_BUSY` instead. `reindex` and
  `recover_orphans` are background jobs that emit `progress` per message and
  a terminal `job_complete` with what they repaired; they migrate the archive
  when they open it, exactly like the CLI, and report `MIGRATION_ERROR` if
  the schema is newer than this build.
- `migrate_status` reports on-disk schema versions and pending steps in
  dry-run mode. `backup`, `verify_backup` and `restore` are background jobs
  that validate before publishing; failures report `BACKUP_FAILED`,
  `BACKUP_INVALID` or `RESTORE_FAILED`, and missing paths are rejected as
  `INVALID_PARAMS` before a job starts.
- `message` and `thread` results carry the body text and indexed attachment
  metadata (`filename`, `mime`, `characters`); an archive without the
  attachment index reports an empty list rather than failing.
- Parameters are validated; unknown methods and versions are rejected.

## Alternatives considered

- **Local HTTP API:** rejected for the first PoC — larger attack surface and
  requires binding/port management for no demonstrated benefit.
- **Python object serialization over a pipe (pickle):** rejected — not
  inspectable, not safe for untrusted boundaries.

## Shell-side event delivery

The Rust bridge registers `engine-event` with the webview for every engine
line that carries `event` instead of `request_id`, so background job
progress and completion reach Vue components through
`@tauri-apps/api/event` rather than polling. Job identifiers are returned by
the starting request and used to filter events.

Events are asynchronous: a fast job can emit `progress` and even its
terminal event before the start response reaches the client. Consumers must
buffer events by `job_id` (`frontend/src/composables/useEngineJob.ts` does
this) instead of assuming the response arrives first.

## Consequences

- The protocol is inspectable and testable without a GUI (subprocess or
  in-process tests).
- No unrestricted SQL, shell, filesystem, or Python execution is exposed.
- The frontend must speak JSON lines; a small client abstraction is needed
  on the shell side.
- Cancellation is cooperative: jobs check a cancel flag between items.
