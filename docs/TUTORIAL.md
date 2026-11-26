# HB Dispatch: Take ownership of your email history

## 1. Why an archive is different from an inbox

Imagine changing internet providers, retiring an old domain, reaching a mailbox quota, or needing to find an agreement from five years ago. Your mail provider may be excellent at delivering today's messages, yet your historical correspondence remains dependent on that provider.

HB Dispatch separates **communication** from **record keeping**. Continue using your favorite mail client to send and receive. Use Dispatch to build a searchable, independent collection of original messages on storage you control.

A useful mental model:

```
Mail providers and exported EML files
             |
       read-only retrieval / import
             |
    HB Dispatch local archive
       |                 |
    original EML      SQLite search index
       |
    independent encrypted backup
```

This is not a replacement mail client, cloud backup service, or automated mailbox cleaner. It is an experimental local-first archive and research workstation.

## 2. Start with a disposable practice archive

Install Python 3.12 or newer with SQLite FTS5 support. Tkinter is optional for desktop browsing; some Linux distributions package it separately. From a terminal:

```sh
git clone https://github.com/James-HoneyBadger/HB_Dispatch.git
cd HB_Dispatch
python3 --version
python3 -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(body)'); print('FTS5 available')"
python3 dispatch.py --version
python3 -m unittest discover -s tests -v
```

Examples below use a POSIX shell (Linux/macOS); on Windows use your Python launcher and equivalent paths. Main is the public beta and the source of the [v0.3.0 release](https://github.com/James-HoneyBadger/HB_Dispatch/releases/tag/v0.3.0); anything on a public development branch beyond that tag is an alpha experiment that is not part of it.

Create a synthetic email outside the repository using a plain-text editor, saving it as `~/dispatch-practice.eml` (not .txt):

```text
From: Accounts <accounts@example.invalid>
To: Reader <reader@example.invalid>
Subject: Invoice 1042 payment confirmation
Date: Tue, 10 Nov 2026 10:00:00 +0000
Message-ID: <practice-1042@example.invalid>
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8

Invoice 1042 was paid in full.
This is fictional correspondence for a tutorial.
```

Import it, search, and verify:

```sh
python3 dispatch.py --archive ~/dispatch-practice import ~/dispatch-practice.eml
python3 dispatch.py --archive ~/dispatch-practice search invoice
python3 dispatch.py --archive ~/dispatch-practice verify
```

The import prints a 64-character SHA-256 hash. Search returns JSON rows containing the hash, subject and sender. Verify prints an empty JSON array when every indexed raw message exists and matches its expected hash; otherwise it lists problematic hashes and exits unsuccessfully. Import the identical file again: the same raw bytes produce the same hash and only one indexed message.

The archive directory contains `raw/<hash>.eml` and `archive.sqlite3`. The original message is retained as received or imported, including headers and MIME attachments. The search index is a derived representation, not a substitute for the original. Imported files do not automatically acquire IMAP account/folder provenance.

## 3. Find things without opening a webmail account

```sh
python3 dispatch.py --archive ~/dispatch-practice search 'invoice'
python3 dispatch.py --archive ~/dispatch-practice search '"paid in full"'
python3 dispatch.py --archive ~/dispatch-practice search 'invoice AND payment'
python3 dispatch.py --archive ~/dispatch-practice search 'subject:invoice'
python3 dispatch.py --archive ~/dispatch-practice search 'sender:accounts'
python3 dispatch.py --archive ~/dispatch-practice gui
```

Search uses SQLite FTS5 over subject, sender and plain-text body. Search returns up to 100 matches; it is not an exhaustive report. HTML-only messages may lack searchable body text; attachment contents and all headers are not indexed. The GUI lets you import EML files, search and select messages to read their plain-text content. It does not execute HTML or open attachments.

## 4. Connect a real mailbox, cautiously

First back up your existing mail independently using your provider or trusted mail client. Use a new archive outside the source tree, ideally on encrypted storage. Start with a small test folder containing non-sensitive messages.

Obtain your provider's IMAP hostname, username and supported authentication method. Dispatch currently uses implicit TLS on port 993 and prompts for a password at the terminal. It does not store that password. Some providers require application-specific passwords or prohibit password-based IMAP. Native OAuth is not implemented; do not weaken account security to make a connection work.

```sh
python3 dispatch.py --archive ~/MailArchive sync imap.example.invalid reader@example.invalid --folder DispatchTest
```

Replace the fictional host and username with your own. The folder must already exist on the server. A successful sync prints the number of newly fetched messages. Read-only folder selection and BODY.PEEK are used to avoid deleting messages or marking them read. The first sync examines all messages in the selected folder; there is no date or message-count filter. A large folder can require substantial time and storage. Repeating sync skips already recorded folder UIDs within the same UIDVALIDITY epoch.

After checking the test folder, repeat for INBOX and other folders using their exact server-side IMAP names, including Sent and archives. There is no automatic folder discovery or all-folder sync yet. Do not assume INBOX includes sent mail.

### Google accounts

Personal Gmail and Google-hosted custom-domain accounts normally use imap.gmail.com and the full email address. Where permitted, a Google app password can be created after enabling 2-Step Verification. Organization policy or account security may prohibit app passwords; consult Google's official account help. If password-based access is unavailable, export original EML via a trusted client or wait for OAuth support. A Gmail Takeout MBOX file is not a supported direct import format today.

Official help: https://support.google.com/accounts/answer/185833

Gmail labels may appear as overlapping IMAP folders. Check actual folder names in your mail client; do not blindly sync every label. An All Mail folder may be useful but can be enormous and does not necessarily include Spam or Trash.

## 5. Several providers, one searchable history

Run separate sync commands against the same archive:

```sh
python3 dispatch.py --archive ~/MailArchive sync imap.provider-one.invalid reader@example.invalid --folder INBOX
python3 dispatch.py --archive ~/MailArchive sync imap.provider-two.invalid reader@example.org --folder INBOX
python3 dispatch.py --archive ~/MailArchive search 'renewal OR cancellation'
```

These are fictional settings. Each run prompts for that account's credentials. Origins retain host/user, folder, UIDVALIDITY and UID; identical raw message bytes share one hash and can have multiple origins. Forwarding, added headers or message changes may produce a different hash even when the human-visible text is identical. Do not mistake byte-level deduplication for semantic deduplication.

This manual workflow is available now. Saved account profiles, automatic scheduling, OAuth, credential vault integration and unified account/folder management are future goals. Use separate archives for different people or security boundaries; a unified archive is not access-controlled per mailbox.

## 6. Real-world research: reconstruct a disputed invoice

Suppose you receive a bill, request a correction, receive a promise, and later get another bill. Rather than hunting through multiple webmail interfaces, search your archive for the invoice identifier, sender and key phrases. Review original headers and dates using the raw EML files. A message's declared date and sender are not independently authenticated facts.

Use search results to identify the relevant message hashes. To export the synthetic practice message:

```sh
python3 dispatch.py --archive ~/dispatch-practice search invoice
python3 dispatch.py --archive ~/dispatch-practice export ~/dispatch-practice-export REPLACE_WITH_FULL_HASH
```

Replace REPLACE_WITH_FULL_HASH with the actual 64-character hash from your search. The destination must not exist. For a multi-message export, supply multiple hashes after the destination. The export contains original EML files and manifest.json with hashes, filenames and recorded IMAP origins (empty for manual imports). Inspect all outputs; export prevalidates inputs and cleans up on ordinary export exceptions; interrupted processes may still require manual cleanup.

This is useful for personal records, warranty disputes, research, project history and audit preparation. Hashes detect changes relative to the stored hash, not the truth of message contents, authorship, completeness, receipt time, or a legally certified chain of custody. An export may contain private identifiers and attachments; review it before sharing. Redact derivative copies, never the preserved originals.

## 7. Storage independence and backup

Your provider's quota need not dictate the size of your long-term local archive. But downloading is not the same as establishing a recoverable backup.

1. Close Dispatch and stop all sync processes.
2. Copy the entire archive directory, including raw files and SQLite database, to independent encrypted storage.
3. Open a separate restored copy with `--archive`, run verify, search representative messages and inspect attachments safely using a trusted tool.
4. Compare folder coverage against your provider and independently confirm important messages, dates and attachments. Verification alone cannot find mail that was never downloaded or unindexed orphan files.
5. Maintain multiple backup copies, including one independent of your primary machine. Test recovery periodically.

For example, with the application closed, copy ~/MailArchive to a fresh directory using your operating system's backup tool, then run:

```sh
python3 dispatch.py --archive ~/MailArchive-restored verify
python3 dispatch.py --archive ~/MailArchive-restored search invoice
```

Use the actual restored path. Disk encryption and backup access controls are your responsibility; Dispatch does not encrypt its database or raw mail. Never put real archives, credentials or exports in a Git repository. Do not open unexpected attachments or load remote HTML from archived mail.

**Do not delete server copies based solely on this experimental application.** Verified mailbox re-upload, automated retention and server cleanup are not implemented. Keep your established independent backup and recovery process.

## 8. What is available today, and what is coming?

| Capability | Public main |
| --- | --- |
| EML import, local original storage | Available |
| SHA-256 exact-byte deduplication | Available |
| Plain-text full-text search and desktop viewer | Available |
| Explicit read-only IMAP sync, one folder per run | Implemented; live-provider validation pending |
| Multiple accounts in one archive via separate commands | Implemented; live-provider validation pending |
| Hash verification and EML/manifest export | Available, with limitations |
| Correspondent summaries, reply graph and timeline | Implemented in desktop UI; validation pending |
| Attachment-content indexing, saved account profiles, OAuth | Planned |
| Automatic retention, complete recovery workflows | Planned |

Public alpha branches invite experimentation, not reliance. The current main branch remains experimental; see README limitations. No service account, telemetry, subscription, or mandatory cloud search is required.

## 9. A daily habit, not a new email provider

Continue reading and replying in your usual client. Periodically retrieve relevant folders, verify your local archive, and maintain independent backups. When you need to find old correspondence, search your own copy instead of depending exclusively on the provider.

The long-term objective is simple: **your email provider transports your correspondence; you retain control of its history.**
