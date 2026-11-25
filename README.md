# HB_Dispatch

Experimental local-first email archive and evidence research workstation. Early-stage release — read the limitations below.

## Quick start

Python 3.12+ with SQLite FTS5 and optional Tkinter.

```sh
python3 dispatch.py import sample.eml
python3 dispatch.py search invoice
python3 dispatch.py verify
python3 dispatch.py gui
python3 dispatch.py sync imap.example.invalid user@example.invalid --folder INBOX
python3 dispatch.py export evidence HASH
python3 -m unittest discover -s tests -v
```

Use `--archive PATH` before the subcommand to select storage. Sync uses TLS, read-only mailbox selection and BODY.PEEK. Passwords are prompted for, never stored by the application. Provider-specific authentication may be required. Gmail OAuth, Keychain and MCP are future work.

## Privacy and limitations

Original EML files are preserved by SHA-256 with SQLite search and mailbox provenance. Hashes detect changes, not authenticity or certified chain of custody. No telemetry or sending. HTML is not rendered. Use an encrypted disk and keep all real mail and credentials outside the repository. Back up the entire archive with the app closed. Failed imports may leave unindexed raw files; failed exports may be partial. Live IMAP and GUI are unverified. Resource limits, atomic exports, attachment and thread UI, and broader hostile-MIME hardening remain future work. Do not use as the sole evidence archive or for untrusted bulk imports yet.
