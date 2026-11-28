# Security review checklist

A focused entry point for an independent reviewer. It covers the two most
sensitive areas so the whole codebase does not need reading first. Every claim
here was checked against the tree at `v0.5.0-beta`.

Nothing in this document claims that a review has happened.

## Scope

### Encryption

| Path | Why it matters |
| --- | --- |
| `hb_engine/encryption.py` | Archive creation, scrypt derivation, descriptor file, unlock and lock |
| `hb_engine/db.py` | Central connection service; SQLCipher pragmas and the session key |
| `hb_engine/backup.py` | Snapshot, validation and restore, including encrypted snapshots |
| `hb_engine/migration.py` | Plaintext-to-encrypted migration, validation and recovery |
| `scripts/security_review_vectors.sh` | The reproducible vector used below |

### Credentials

| Path | Why it matters |
| --- | --- |
| `hb_engine/schedulers.py` | Keychain, keyring and the opt-in encrypted-file store |
| `hb_engine/schedule.py` | CLI wiring, including `--allow-insecure-credential-fallback` |
| `tests/test_schedulers.py` | Fail-closed, opt-in warning, tamper and plaintext-scan tests |

### Out of scope for pass one

Vue frontend, the Tauri Rust shell, third-party dependencies (report those
upstream), packaging and installer behaviour, and anything requiring a
compromised host with the archive already unlocked.

## Threat-model prompts the reviewer should answer

1. Can an attacker with read access to the archive directory recover plaintext
   without the key?
2. How is the SQLCipher key obtained — passphrase-derived or keyring-stored?
   Which KDF, which parameters, and how is the salt handled?
3. What happens when the OS keyring is unavailable — fail closed, or fall back?
   Where in the code is that decision made?
4. Which data sits outside the encryption boundary, and is that surfaced in
   the application?
5. Can the backup path leak plaintext, and is a restore verified before it
   overwrites anything?
6. Is authenticated-encryption usage correct: unique nonces, authenticated
   associated data, no reuse across archives?

## Test vectors

All commands run from a repository checkout. `PYTHON` selects the interpreter;
the encrypted steps require `sqlcipher3`.

```sh
PYTHON=python3 ./scripts/security_review_vectors.sh          # plaintext vectors
PYTHON=/path/to/python-with-sqlcipher3 ./scripts/security_review_vectors.sh
```

Fixed values:

| Item | Value |
| --- | --- |
| Passphrase | `security-review-vector-passphrase` |
| Fixture | `tests/fixtures/security_review/fictional-2023-03-14.eml` |
| Fixture size | 595 bytes |
| Fixture SHA-256 | `653eef314e3ce4374eff51724ecd6d75a4c82370262a409030329f3fe78919f2` |

The script proves, in order: fixture integrity; plaintext import, search and
verification; encrypted creation; encrypted import and search; that ordinary
`sqlite3` and the file header do not reveal a SQLite database; that a wrong
passphrase returns no records and a non-zero status; encrypted backup;
verification of that backup; restore into a new location; and an identical
search on the restored archive.

To inspect the encrypted database directly:

```sh
sqlcipher /path/to/archive/archive.sqlite3
PRAGMA key = 'security-review-vector-passphrase';
PRAGMA cipher_version;
SELECT count(*) FROM sqlite_master;
```

## Reporting template

```
Severity: Critical / High / Medium / Low
Component: (e.g. hb_engine/encryption.py unlock)
Reproduction steps:
Impact:
Suggested remediation:
Credit: (name or "anonymous")
```

## Response expectations

Restated from [SECURITY.md](SECURITY.md): acknowledgement within 72 hours, best
effort; initial assessment within 7 days; fix best effort, prioritised by
severity and exploitability. There is no bounty, no paid support and no
guaranteed fix deadline. Coordinated disclosure is preferred; reporters may
publish after a fix ships or after 90 days without one, whichever comes first.
