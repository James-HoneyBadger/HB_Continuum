# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Portable background scheduling and credential storage.

Generated unit files and task definitions contain only the synchronization
command line. Passwords are never written to them; they are resolved from
the operating system credential store when a job runs.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

class SchedulerError(RuntimeError):
    pass

def archive_id(root):
    return hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]

def sync_command(root, account=None):
    """Command line a scheduler should run; contains no credentials."""
    script = Path(__file__).resolve().with_name('schedule.py')
    parts = [sys.executable, str(script), '--archive', str(Path(root).resolve())]
    parts += ['run', account] if account else ['tick']
    return parts

def _quote(parts):
    return ' '.join('"' + p + '"' if (' ' in p or '"' in p) else p for p in parts)

def _run(args, check=True):
    try:
        result = subprocess.run(args, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SchedulerError(f'{args[0]} failed: {exc}') from None
    if check and result.returncode:
        detail = result.stderr.decode('utf-8', 'replace').strip() or result.stdout.decode('utf-8', 'replace').strip()
        raise SchedulerError(f'{args[0]} exited {result.returncode}: {detail}')
    return result

# ---------------------------------------------------------------- schedulers

class LaunchdScheduler:
    """macOS launchd agent (reference implementation)."""
    name = 'launchd'
    platform = 'darwin'

    def __init__(self, home=None):
        self.home = Path(home) if home is not None else Path.home()

    def label(self, root):
        return 'org.honeybadger.dispatch.' + archive_id(root)

    def path(self, root):
        return self.home / 'Library' / 'LaunchAgents' / (self.label(root) + '.plist')

    def install(self, root, account=None, interval=None, every=None, at=None):
        import plistlib
        path = self.path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SchedulerError('Agent file already exists; remove the scheduler, then install again')
        data = {'Label': self.label(root),
                'ProgramArguments': sync_command(root, account),
                'RunAtLoad': True, 'ProcessType': 'Background'}
        if every:
            data['StartInterval'] = int(every) * 60
        elif at:
            hour, minute = at.split(':')
            data['StartCalendarInterval'] = {'Hour': int(hour), 'Minute': int(minute)}
        else:
            data['StartInterval'] = 60
        with path.open('xb') as f:
            plistlib.dump(data, f)
        try:
            _run(['/bin/launchctl', 'bootstrap', 'gui/' + str(os.getuid()), str(path)])
        except SchedulerError:
            path.unlink(missing_ok=True)
            raise
        return str(path)

    def uninstall(self, root, account=None):
        path = self.path(root)
        if self.status(root) == 'Loaded':
            _run(['/bin/launchctl', 'bootout', 'gui/' + str(os.getuid()) + '/' + self.label(root)])
        path.unlink(missing_ok=True)

    def status(self, root, account=None):
        path = self.path(root)
        result = _run(['/bin/launchctl', 'print',
                       'gui/' + str(os.getuid()) + '/' + self.label(root)], check=False)
        if result.returncode == 0:
            return 'Loaded'
        return 'Installed, not loaded' if path.exists() else 'Not installed'

class SystemdScheduler:
    """Linux systemd --user timer unit."""
    name = 'systemd'
    platform = 'linux'

    def __init__(self, home=None):
        self.home = Path(home) if home is not None else Path.home()

    def unit_dir(self):
        config_home = os.environ.get('XDG_CONFIG_HOME')
        base = Path(config_home) if config_home else self.home / '.config'
        return base / 'systemd' / 'user'

    def base(self, root):
        return 'hb-dispatch-' + archive_id(root)

    def service_path(self, root):
        return self.unit_dir() / (self.base(root) + '.service')

    def timer_path(self, root):
        return self.unit_dir() / (self.base(root) + '.timer')

    def _timer_section(self, every=None, at=None):
        if every:
            return f'OnUnitActiveSec={int(every)}min\nOnBootSec=5min'
        if at:
            hour, minute = at.split(':')
            return f'OnCalendar=*-*-* {int(hour):02d}:{int(minute):02d}:00'
        return 'OnCalendar=daily'

    def install(self, root, account=None, interval=None, every=None, at=None):
        self._require_user_session()
        self.unit_dir().mkdir(parents=True, exist_ok=True)
        service = ('[Unit]\n'
                   'Description=HB Continuum mailbox synchronization\n'
                   'After=network-online.target\n\n'
                   '[Service]\n'
                   'Type=oneshot\n'
                   f'ExecStart={_quote(sync_command(root, account))}\n')
        timer = ('[Unit]\n'
                 'Description=HB Continuum synchronization timer\n\n'
                 '[Timer]\n'
                 f'{self._timer_section(every, at)}\n'
                 'Persistent=true\n\n'
                 '[Install]\n'
                 'WantedBy=timers.target\n')
        self.service_path(root).write_text(service, encoding='utf-8')
        self.timer_path(root).write_text(timer, encoding='utf-8')
        try:
            _run(['systemctl', '--user', 'daemon-reload'])
            _run(['systemctl', '--user', 'enable', '--now', self.base(root) + '.timer'])
        except SchedulerError as exc:
            unit = self.base(root) + '.timer'
            _run(['systemctl', '--user', 'disable', '--now', unit], check=False)
            self.timer_path(root).unlink(missing_ok=True)
            self.service_path(root).unlink(missing_ok=True)
            self._wants_link(root).unlink(missing_ok=True)
            _run(['systemctl', '--user', 'daemon-reload'], check=False)
            if 'bad unit file' in str(exc):
                raise SchedulerError(
                    f'systemd rejected {self.timer_path(root)}: {exc}') from None
            if 'does not exist' in str(exc):
                raise SchedulerError(
                    f'systemd could not load {self.timer_path(root)}. The user manager only '
                    'searches its own configuration path, so install from the account that '
                    'owns the session (and without overriding HOME or XDG_CONFIG_HOME).'
                ) from None
            raise
        return str(self.timer_path(root))

    def _wants_link(self, root):
        return self.unit_dir() / 'timers.target.wants' / (self.base(root) + '.timer')

    def _require_user_session(self):
        result = _run(['systemctl', '--user', 'show-environment'], check=False)
        if result.returncode:
            raise SchedulerError(
                'No systemd user session is available for this account. Run this from a '
                'logged-in desktop session, or enable lingering with: '
                'loginctl enable-linger $USER')

    def uninstall(self, root, account=None):
        unit = self.base(root) + '.timer'
        _run(['systemctl', '--user', 'disable', '--now', unit], check=False)
        self.timer_path(root).unlink(missing_ok=True)
        self.service_path(root).unlink(missing_ok=True)
        self._wants_link(root).unlink(missing_ok=True)
        if self.unit_dir().is_dir():
            _run(['systemctl', '--user', 'daemon-reload'], check=False)

    def status(self, root, account=None):
        if not self.timer_path(root).exists():
            return 'Not installed'
        result = _run(['systemctl', '--user', 'is-active', self.base(root) + '.timer'], check=False)
        state = result.stdout.decode('utf-8', 'replace').strip()
        return state or ('Installed, not active' if result.returncode else 'active')

class SchtasksScheduler:
    """Windows Task Scheduler via schtasks."""
    name = 'schtasks'
    platform = 'win32'

    def __init__(self, home=None):
        self.home = Path(home) if home is not None else Path.home()

    def task_name(self, root):
        return 'HBContinuumSync-' + archive_id(root)

    def install(self, root, account=None, interval=None, every=None, at=None):
        args = ['schtasks', '/Create', '/F', '/TN', self.task_name(root),
                '/TR', _quote(sync_command(root, account))]
        if every:
            args += ['/SC', 'MINUTE', '/MO', str(int(every))]
        else:
            args += ['/SC', 'DAILY', '/ST', at or '12:00']
        _run(args)
        return self.task_name(root)

    def uninstall(self, root, account=None):
        _run(['schtasks', '/Delete', '/F', '/TN', self.task_name(root)], check=False)

    def status(self, root, account=None):
        result = _run(['schtasks', '/Query', '/TN', self.task_name(root)], check=False)
        if result.returncode:
            return 'Not installed'
        text = result.stdout.decode('utf-8', 'replace')
        for state in ('Running', 'Ready', 'Disabled'):
            if state in text:
                return state
        return 'Installed'

def get_scheduler(home=None):
    if sys.platform == 'darwin':
        return LaunchdScheduler(home)
    if sys.platform.startswith('linux'):
        return SystemdScheduler(home)
    if sys.platform in ('win32', 'cygwin'):
        return SchtasksScheduler(home)
    raise SchedulerError(f'No scheduler for platform {sys.platform!r}')

# ------------------------------------------------------------ credentials

class KeychainCredentialStore:
    """macOS login Keychain through the security tool."""
    name = 'keychain'
    platform = 'darwin'

    def get(self, service, account, root=None):
        result = _run(['/usr/bin/security', 'find-generic-password', '-s', service,
                       '-a', account, '-w'], check=False)
        if result.returncode:
            raise SchedulerError('Keychain credential unavailable')
        return result.stdout.decode('utf-8', 'replace').rstrip('\r\n')

    def set(self, service, account, secret, root=None):
        _run(['/usr/bin/security', 'add-generic-password', '-U', '-s', service,
              '-a', account, '-w', secret])

    def delete(self, service, account, root=None):
        _run(['/usr/bin/security', 'delete-generic-password', '-s', service,
              '-a', account], check=False)

class KeyringCredentialStore:
    """SecretService (Linux) or Credential Manager (Windows) via keyring."""
    name = 'keyring'

    @staticmethod
    def available():
        try:
            import keyring  # noqa: F401
        except Exception:
            return False
        return True

    def get(self, service, account, root=None):
        import keyring
        try:
            secret = keyring.get_password(service, account)
        except Exception as exc:
            raise SchedulerError(f'keyring unavailable: {exc}') from None
        if not secret:
            raise SchedulerError(f'no stored credential for {account} ({service})')
        return secret

    def set(self, service, account, secret, root=None):
        import keyring
        try:
            keyring.set_password(service, account, secret)
        except Exception as exc:
            raise SchedulerError(f'keyring unavailable: {exc}') from None

    def delete(self, service, account, root=None):
        import keyring
        try:
            keyring.delete_password(service, account)
        except Exception as exc:
            raise SchedulerError(f'keyring unavailable: {exc}') from None

class EncryptedFileCredentialStore:
    """Degraded fallback: Fernet-encrypted secrets under the archive directory.

    The master key is a 0600 file beside the ciphertext, so this protects
    against casual inspection and accidental copying, not against an attacker
    who can already read the user's home directory. Prefer keyring.
    """
    name = 'encrypted-file'

    @staticmethod
    def available():
        try:
            import cryptography.fernet  # noqa: F401
        except Exception:
            return False
        return True

    def _paths(self, root):
        if root is None:
            raise SchedulerError('encrypted-file credentials require an archive root')
        base = Path(root)
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        return base / 'credentials.key', base / 'credentials.enc'

    def _fernet(self, root):
        from cryptography.fernet import Fernet
        key_path, _ = self._paths(root)
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(key)
        return Fernet(key)

    def _load(self, root):
        _, path = self._paths(root)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding='utf-8'))

    def _save(self, root, data):
        _, path = self._paths(root)
        tmp = path.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, path)

    def get(self, service, account, root=None):
        token = self._load(root).get(service + '\0' + account)
        if not token:
            raise SchedulerError(f'no stored credential for {account} ({service})')
        from cryptography.fernet import InvalidToken
        try:
            return self._fernet(root).decrypt(token.encode('ascii')).decode('utf-8')
        except InvalidToken:
            raise SchedulerError('stored credential cannot be decrypted') from None

    def set(self, service, account, secret, root=None):
        data = self._load(root)
        data[service + '\0' + account] = self._fernet(root).encrypt(secret.encode('utf-8')).decode('ascii')
        self._save(root, data)

    def delete(self, service, account, root=None):
        data = self._load(root)
        if data.pop(service + '\0' + account, None) is not None:
            self._save(root, data)

def get_credential_store(root=None):
    if sys.platform == 'darwin':
        return KeychainCredentialStore()
    if KeyringCredentialStore.available():
        return KeyringCredentialStore()
    if EncryptedFileCredentialStore.available():
        return EncryptedFileCredentialStore()
    raise SchedulerError('No credential store available; install the keyring package')
