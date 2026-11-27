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
  `thread`, `record`, `verify`, `import_eml`, `preferences`,
  `preferences_set`, the `research_*` overlay methods, `export_evidence`,
  the `schedule_*` methods, `summarize`, `cancel` and `shutdown`.
- `message` and `thread` results carry the body text and indexed attachment
  metadata (`filename`, `mime`, `characters`); an archive without the
  attachment index reports an empty list rather than failing.
- Parameters are validated; unknown methods and versions are rejected.

## Alternatives considered

- **Local HTTP API:** rejected for the first PoC — larger attack surface and
  requires binding/port management for no demonstrated benefit.
- **Python object serialization over a pipe (pickle):** rejected — not
  inspectable, not safe for untrusted boundaries.

## Consequences

- The protocol is inspectable and testable without a GUI (subprocess or
  in-process tests).
- No unrestricted SQL, shell, filesystem, or Python execution is exposed.
- The frontend must speak JSON lines; a small client abstraction is needed
  on the shell side.
- Cancellation is cooperative: jobs check a cancel flag between items.
