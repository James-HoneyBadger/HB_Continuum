# Security model and threat boundaries

HB Continuum is a local-first hobby FOSS application. This document describes
what the current encryption work protects, what it does not protect, and the
limits that remain while an archive is unlocked or the host is compromised.

It is not a security certification.

## Assets

- Email databases, full-text indexes, provenance and import history.
- Catalog records for Facebook exports and imported documents.
- Research workspaces, collections, journals, saved queries and conversations.
- Original EML files under `raw/`.
- External documents referenced by path.
- Attachments and extracted document text.
- Preferences, schedules and synchronization configuration.
- Backups, exports, reports and model-related derived text.
- Archive passwords and derived keys.

## Protections implemented

- New archives can be created with SQLCipher-encrypted
  `archive.sqlite3`, `research.sqlite3` and `catalog.sqlite3`.
- Existing plaintext archives can be explicitly migrated to a separate
  encrypted destination. The original is never deleted automatically.
- Passwords are prompted for, never accepted as command-line arguments, and
  are never written to preferences, logs, Git or ordinary files.
- Passwords derive a 32-byte key with scrypt and a random salt. Only the public
  salt and KDF parameters are stored.
- Keys are held only in process memory. Explicit locking clears the in-memory
  key. The desktop lock action is refused while background jobs are active.
- Encrypted backups keep database files encrypted; restore does not silently
  create plaintext databases.
- Raw EML files and external documents remain plaintext. Full-disk or
  encrypted-container protection is recommended for those files.
- SQLite temporary storage for encrypted connections is memory-backed, and
  SQLCipher memory security is enabled.
- Scheduled synchronization defers instead of bypassing a locked encrypted
  archive. It does not attempt to obtain the archive password.
- No telemetry, advertising or mandatory cloud account is built in.
- Model inference is optional, local and loopback-only; evidence is treated as
  untrusted data and model output cannot modify the archive.

## What is not protected

### Plaintext files outside the databases

Original EML files under `raw/`, external documents imported by path,
preferences, schedule files, configuration, exports, reports, collection
manifests, conversation JSON and plaintext backups remain readable by anyone
with filesystem access. Database encryption does not protect them.

### While the archive is unlocked

When the archive is unlocked, the derived key and opened database pages exist
in process memory. Any code or user that can read the process, inspect memory,
attach a debugger, log keystrokes or access the mounted files can read the
archive. Locking only helps after it succeeds; it cannot erase copies already
made by another process.

### Compromised host

Encryption at rest does not defend against a compromised operating system,
malware running as the user, memory scraping, keyloggers, screen capture,
malicious extensions, or an attacker who can read the unlocked process. It also
does not protect against a compromised backup, a plaintext legacy copy, or a
filesystem snapshot made while the archive was plaintext.

### Passwords

There is no password recovery, reset, key rotation or multi-user access control.
A weak password can be attacked offline against a copied encrypted database.
If the password is lost, the encrypted destination cannot be opened by the
application; the original plaintext archive and any plaintext backup are the
recovery path.

### Backups and old copies

Encrypted archive backups reuse the archive key and keep database files
encrypted. Raw EML files, configuration and reports in a snapshot remain
plaintext. Older backups, filesystem snapshots and exported `.eml` files may
still contain plaintext data after migration. The application never deletes
them automatically.

### Local AI

Ollama inference is optional and loopback-only. Evidence sent to a local Ollama
process is outside the database encryption boundary while the request is in
memory. The project does not add transport encryption to loopback HTTP. Model
files and any provider-side data are outside this project's control.

### Logs and errors

The application does not intentionally log passwords or keys. Error messages
may include filesystem paths, record identifiers or type names. Do not enable
debugging or memory-dump tools on an unlocked archive unless you accept that
risk.

## Temporary files and staging

- Encrypted database connections use `temp_store=MEMORY`.
- Migration uses hidden staging directories; encrypted database copies and
  plaintext raw/config files exist there until publication or cleanup.
- Import and backup operations use temporary paths that are removed on normal
  completion. An abrupt process termination can leave a temporary directory
  behind; inspect and remove it deliberately.
- A plaintext backup is a deliberate copy of plaintext data.

## macOS encrypted volume guidance

For raw EML files, external documents and other non-database files, prefer an
independently encrypted APFS volume or disk image rather than a custom
application-level file format.

Using Disk Utility:

1. Choose **File → New Image → Blank Image**.
2. Select **APFS** and **256-bit AES encryption**.
3. Choose a sparse bundle or disk image size large enough for the archive,
   raw EML files, external documents and backups.
4. Mount the image and create/keep the HB Continuum archive inside the mounted
   volume, for example `/Volumes/HB Continuum/archive`.
5. Eject the volume when finished. The archive password and the volume password
   are separate secrets.

Command-line equivalent:

```sh
hdiutil create -type SPARSE -fs APFS -encryption AES-256 \
  -size 20g -volname "HB Continuum" ~/HB-Continuum.sparseimage
hdiutil attach ~/HB-Continuum.sparseimage
# Create and use the archive under /Volumes/HB Continuum/
hdiutil detach "/Volumes/HB Continuum"
```

The application does not create or manage this volume. APFS encryption is an
operating-system feature, not a custom HB Continuum format.

## Recommendations

- Use a long, unique archive password and an encrypted APFS volume for raw
  files and external documents.
- Keep encrypted database backups and plaintext backups separate; label
  plaintext copies clearly.
- Lock the archive when leaving the workstation and rely on full-disk
  encryption for the host.
- Treat exports, reports, manifests, conversation JSON and backups as sensitive.
- Do not use HB Continuum as the sole copy of irreplaceable evidence.
