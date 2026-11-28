# Security policy

HB Continuum stores decades of personal correspondence and documents on the
user's own machine. Security reports are taken seriously. This is a
single-maintainer hobby project in beta: the commitments below are honest
best-effort statements from one person, not an enterprise service level.

## Supported versions

| Version | Supported |
| --- | --- |
| `v0.5.x` | Receives security fixes |
| `v0.4.x` and earlier | Not supported |

Beta releases may change storage formats, defaults and guarantees without
notice. Only the tagged source in this repository is covered; forks and
locally modified builds are not.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the repository's **Security**
tab and choose **Report a vulnerability**.

**Do not open a public issue, pull request or discussion for a suspected
vulnerability.** Public reports can expose users of a project that holds
sensitive personal records.

If private reporting is unavailable, open a public issue that says only that
you have a security report and would like a private channel; do not include
details, proof of concept or affected data.

### What to expect

| Stage | Commitment |
| --- | --- |
| Acknowledgement | Within 72 hours, best effort |
| Initial assessment | Within 7 days |
| Fix | Best effort, prioritised by severity and exploitability |

There is no bug bounty, no paid support and no guaranteed fix deadline. If a
report cannot be fixed promptly it will be documented as a known limitation so
users can decide for themselves.

## Disclosure

Coordinated disclosure is preferred: a fix is prepared and released before
public details appear. Credit is given in the release notes unless anonymity is
requested. Reporters are welcome to publish after a fix ships or after 90 days
without a fix, whichever comes first.

## In scope

- The engine core in `hb_engine/`, including the CLI (`dispatch.py`) and IPC
  server.
- Encryption and key handling: archive creation, unlock and lock, key
  derivation, the encryption descriptor file, encrypted backup and restore, and
  plaintext-to-encrypted migration.
- Credential handling for scheduled synchronization: OS credential store use
  and the opt-in encrypted-file fallback.
- Import and export integrity: hashing, verification, restore paths.
- The Tauri IPC boundary (`src-tauri/`, `hb_engine/ipc.py`), including request
  validation.

## Out of scope

- Third-party dependencies: report those upstream (SQLCipher, `sqlcipher3`,
  `cryptography`, Ollama, Tauri, Vue). This project will still act on reports
  that a dependency choice endangers users.
- Operating-system issues, full-disk encryption failures, and attacks that
  require an already-compromised host with the archive unlocked.
- Data outside the documented encryption boundary, described below.

## What encryption does not cover

Database encryption protects the SQLite databases only. The following remain
outside that boundary and are not protected by an encrypted archive:

- original EML files under the archive's raw store;
- imported external documents and their originals;
- the encryption descriptor, preferences and other configuration files;
- exports, reports and generated files;
- logs and diagnostic output;
- backups taken by other tools.

Anyone who can read those files can read their contents. Use OS full-disk
encryption (FileVault, BitLocker, LUKS) or an encrypted container as well. The
[security model](docs/SECURITY_MODEL.md) records the full threat model.

Credential storage has a related caveat. The scheduler prefers the OS
credential store (Keychain, Secret Service, Credential Manager). Where none is
available it refuses to store a password unless
`--allow-insecure-credential-fallback` is passed; that fallback encrypts the
password with a key kept beside it in the archive directory, so it defends
against casual inspection and accidental copying only.

## Preparing a review

If you are carrying out an independent review, the
[security review checklist](SECURITY_REVIEW_CHECKLIST.md) names the files in
scope, the questions to answer and a reproducible vector script with a
disposable archive and a synthetic fixture.

## No audit has occurred

This project has not been independently audited or penetration tested. Do not
treat the presence of this policy as evidence of review.

## Repository setting for maintainers

Private vulnerability reporting must be enabled once by a repository owner:

- Web: **Settings → Code security and analysis → Private vulnerability
  reporting → Enable**.
- CLI (human executes):
  `gh api -X PUT repos/James-HoneyBadger/HB_Continuum/private-vulnerability-reporting`
