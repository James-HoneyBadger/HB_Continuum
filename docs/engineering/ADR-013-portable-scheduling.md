# ADR-013: Portable scheduling and credential storage

- **Status:** Accepted (implemented in `schedulers.py`)
- **Date:** 2026-11-26

## Context

Scheduled synchronization used macOS launchd and the login Keychain
directly inside `schedule.py`. The directive requires Linux and Windows
support without breaking the macOS path, and forbids storing IMAP passwords
in plaintext in generated unit files.

## Decision

Extract two small interfaces and select an implementation by platform:

- `Scheduler` — `install`, `uninstall`, `status`, with the archive root and
  optional account/interval parameters.
- `CredentialStore` — `get`, `set`, `delete`, taking a service name and
  account.

`schedule.py` keeps its public functions (`install`, `uninstall`,
`agent_status`, `credential`) as thin delegates, so existing callers, tests
and the Tk synchronization center keep working.

Both `tick()` and the credential stores remain platform-neutral; only the
strategies differ. Generated artifacts contain the synchronization command
line only.

## Alternatives considered

- **One in-process scheduler thread instead of OS units:** rejected — loses
  run-at-login and boot persistence, and duplicates what the OS already does.
- **Storing the password in the unit file or an environment variable:**
  rejected outright; visible in process listings and unit files.
- **Requiring `keyring` unconditionally:** rejected — it is an optional
  dependency; the encrypted-file fallback keeps Linux usable, with honest
  documentation of its weaker guarantee.

## Consequences

- Three platform code paths to maintain, but they are small and tested with
  mocked subprocess calls.
- Linux depends on a systemd user session; a clear error explains
  `loginctl enable-linger` when none exists.
- The encrypted-file fallback is a documented degraded mode: a `0600` key
  beside the ciphertext protects against casual inspection, not against an
  attacker who can read the home directory.
- Windows lacks the POSIX archive write lock; a single task instance is the
  only overlap protection there.
- Real installation was verified on Linux systemd; launchd and schtasks
  rely on `scripts/scheduler_smoke.py` in CI for equivalent evidence.
