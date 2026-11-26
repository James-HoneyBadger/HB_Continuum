# Local scheduled synchronization (macOS)

HB Dispatch's synchronization center maintains an existing archive without
ChatGPT, a hosted scheduler, or a permanent terminal window. It uses a
per-user macOS LaunchAgent, the login Keychain and the existing read-only
IMAP importer. Nothing is uploaded except the standard IMAP authentication
and requests sent to your selected mail provider.

## First-time setup

1. Finish any import started with an older version of HB Dispatch. This
   matters because older versions did not participate in the synchronization lock.
2. Start the correspondence workstation with
   `python3 dispatch.py --archive ~/HB_Mail_Archive gui` and select
   **Synchronization center**, or open it directly with
   `python3 schedule.py --archive ~/HB_Mail_Archive gui`.
3. Create a profile for each provider. Enter its IMAP server, exact username
   (matching your prior manual import), and mailbox names separated by semicolons.
   Select an interval of 5–10080 minutes or a daily local time in HH:MM
   format. New GUI profiles are paused by default. Save the profile.
4. Select **Keychain setup**. In macOS Keychain Access, choose the login
   keychain and create a generic password item with the exact service and account
   shown. Use the provider's app-specific password where applicable.
   The name is `HB Dispatch IMAP <lowercase-host>`; the account is your exact
   IMAP username. Never put passwords in command arguments or profile JSON.
5. Select the profile and **Run now** to test the credentials. macOS may
   ask permission for the security utility to read that specific Keychain item.
   Review the request. Unattended jobs require the item to be accessible while
   the login Keychain is unlocked. Do not disable Keychain protections globally.
6. Review the status, enable the profiles you want, then **Install**.
   Installation is explicit; an enabled profile may run immediately.
   The LaunchAgent starts at login, checks due profiles approximately once
   per minute, and runs accounts sequentially. Intervals and daily times
   are editable without reinstalling. Pause/resume affects future runs,
   not a currently running transfer.

## Typical profile values

| Provider | IMAP server | Username | Folder |
|---|---|---|---|
| IONOS | imap.ionos.com | full email address | INBOX |
| Gmail | imap.gmail.com | full email address | [Gmail]/All Mail |
| iCloud | imap.mail.me.com | the username that successfully authenticated | INBOX |

Use actual folder names from the provider. The application now quotes IMAP
mailbox names, including spaces, and removes whitespace from Gmail app
passwords only. Previously quoted origin records are recognized without
redownloading them. Gmail All Mail does not preserve all label metadata.

## Command-line equivalent

```sh
python3 schedule.py --archive ~/HB_Mail_Archive add work imap.example.com me@example.com --folder INBOX --minutes 30
python3 schedule.py --archive ~/HB_Mail_Archive add personal imap.gmail.com me@gmail.com --folder '[Gmail]/All Mail' --daily 02:30
python3 schedule.py --archive ~/HB_Mail_Archive pause personal
python3 schedule.py --archive ~/HB_Mail_Archive run work
python3 schedule.py --archive ~/HB_Mail_Archive status
python3 schedule.py --archive ~/HB_Mail_Archive install
python3 schedule.py --archive ~/HB_Mail_Archive resume personal
```

CLI add creates an enabled profile, so pause it before saving credentials
if the agent is already loaded. Manual run explicitly overrides pause.
To stop future background synchronization, pause every profile or remove
the LaunchAgent with `python3 schedule.py --archive ~/HB_Mail_Archive uninstall`.
Removal may interrupt a running sync; it does not remove account profiles,
credentials, original EML files, or database rows.

## Operation and limits

- IMAP only retrieves messages whose account, folder, UIDVALIDITY and UID
  are not already recorded. It lists all UIDs each run; it does not download
  their contents again. UIDVALIDITY changes may require a fresh scan.
- Scheduled runs and new manual syncs use cooperative POSIX locks. They do
  not prevent an older running executable or arbitrary external programs
  from writing to the archive.
- Interval timing is measured from the last attempt. Daily timing is
  once per local calendar day, at or after the requested time. Missed
  runs while the Mac is asleep or logged out are not replayed; a due run
  occurs when the agent next runs. Failed interval jobs retry on their next
  interval; failed daily jobs retry the next day or via Run now.
- The archive retains emails deleted from the source mailbox. The
  scheduler does not send, move, delete or mark mail read.
- Credentials are looked up from Keychain; only profile metadata and
  last-attempt/success status are saved in the archive's private
  schedule.json and schedule-status.json files. The status count is
  completed-folder imports during the most recent attempt, not a full
  reconciliation. Exceptions are recorded by type, without raw provider responses.
- Keep the repository checkout and Python executable at their installed
  paths; moving them requires removing and reinstalling the LaunchAgent.
  Background scheduling requires macOS and a logged-in user session.
- The schedule is not a backup. Back up the archive to independent,
  encrypted storage when synchronization is stopped and test restoration.
  Use the existing verify command for raw SHA-256 verification.
- Do not commit archive contents, account configuration, or credentials.
  This feature does not need a ChatGPT connection.

This implementation is subject to provider limits and the existing
64 MiB per-message limit. A locked Keychain, authentication failure,
network outage or provider throttling can prevent a run. Review status
regularly; a failed job does not erase previously archived data.
