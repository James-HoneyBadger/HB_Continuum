# Local scheduled synchronization

HB Continuum's synchronization center maintains an existing archive without
a hosted scheduler or a permanent terminal window. It uses a per-user
platform scheduler, the operating system credential store and the existing
read-only IMAP importer. Nothing is uploaded except the standard IMAP
authentication and requests sent to your selected mail provider.

| Platform | Scheduler | Credential store |
|---|---|---|
| macOS | launchd agent (`LaunchAgents/*.plist`) | login Keychain (`security`) |
| Linux | `systemd --user` service + timer | SecretService via `keyring`; Fernet-encrypted file fallback |
| Windows | Task Scheduler (`schtasks`) | Windows Credential Manager via `keyring` |
| other | not supported (clear error) | `keyring`, else encrypted file |

Generated unit files, task definitions and profiles never contain a password.
Only the synchronization command line is written; credentials are resolved
from the store when a job runs.

## Platform notes and limitations

- **Linux** requires a running systemd user session. Install from the account
  that owns that session; overriding `HOME` or `XDG_CONFIG_HOME` desynchronizes
  the unit path from the user manager. Headless servers need
  `loginctl enable-linger $USER`. Units live in
  `$XDG_CONFIG_HOME/systemd/user` (default `~/.config/systemd/user`).
- **Encrypted-file fallback** stores a Fernet key and ciphertext as `0600`
  files inside the archive directory. It protects against casual inspection
  and accidental copying, not against an attacker who can already read your
  home directory. Prefer `keyring` (install with `pip install keyring`).
- **Windows** tasks run as the logged-in user; `schtasks` definitions are
  visible to other administrators. `keyring` uses Credential Manager.
- **Locking** between overlapping runs is POSIX-only (`sync_lock.py`); Windows
  relies on the single task instance rather than an archive lock.

## Verifying a platform

`scripts/scheduler_smoke.py` installs a real entry, checks its status and
the generated files, then removes it. It exits 0 when verified or when the
environment cannot host a scheduler (printing why), and 1 on a genuine
defect. CI runs it on Ubuntu, macOS and Windows.

```sh
python3 scripts/scheduler_smoke.py
```

## First-time setup

1. Finish any import started with an older version of HB Continuum (formerly HB Dispatch). This
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
   The name is `HB Continuum IMAP <lowercase-host>`; the account is your exact
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

## Command-line installation

```sh
python3 dispatch.py --archive ~/HB_Mail_Archive schedule add work imap.example.invalid user@example.invalid --folder INBOX --minutes 30
python3 dispatch.py --archive ~/HB_Mail_Archive schedule credential set work
python3 dispatch.py --archive ~/HB_Mail_Archive schedule install --account work
python3 dispatch.py --archive ~/HB_Mail_Archive schedule status
python3 dispatch.py --archive ~/HB_Mail_Archive schedule uninstall
```

`install` accepts `--interval minutes --every N` or `--interval daily --at HH:MM`.
With no interval given it adopts the account's profile schedule, and otherwise
defaults to daily. `schedule credential set` prompts for the password and
writes it to the platform store; it is never echoed or stored in a file on
macOS or when `keyring` is available.

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
  paths; moving them requires reinstalling the scheduler entry.
  Background scheduling requires a logged-in user session (macOS, Linux) or
  an available Task Scheduler service (Windows).
- The schedule is not a backup. Back up the archive to independent,
  encrypted storage when synchronization is stopped and test restoration.
  Use the existing verify command for raw SHA-256 verification.
- Do not commit archive contents, account configuration, or credentials.
  Nothing is sent to any third party beyond your own mail provider.

This implementation is subject to provider limits and the existing
64 MiB per-message limit. A locked Keychain, authentication failure,
network outage or provider throttling can prevent a run. Review status
regularly; a failed job does not erase previously archived data.
