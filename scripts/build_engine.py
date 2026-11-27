#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Build the standalone engine binary bundled with the desktop shell.

Run from anywhere:

    python3 scripts/build_engine.py

The script builds `dist/hb-engine` with PyInstaller from `dispatch.py`, then
copies it to `src-tauri/binaries/hb-engine-<rust-host-triple>` where Tauri's
`externalBin` expects a sidecar. The shell prefers that binary and falls back
to `python3 dispatch.py` during development.

The binary is host-specific; build it on each target platform (or per
architecture for macOS universal builds) before packaging the app.
"""
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPTIONAL_MODULES = ('keyring', 'cryptography', 'tkinter')


def engine_name(platform=None):
    return 'hb-engine.exe' if (platform or sys.platform) == 'win32' else 'hb-engine'


def external_bin_name(triple, platform=None):
    return f'hb-engine-{triple}' + ('.exe' if (platform or sys.platform) == 'win32' else '')


def rust_target_triple(run=subprocess.run):
    try:
        completed = run(['rustc', '-vV'], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit('rustc is required to name the sidecar: ' + str(exc)) from None
    for line in completed.stdout.splitlines():
        if line.startswith('host: '):
            return line.split(': ', 1)[1].strip()
    raise SystemExit('rustc did not report a host triple')


def pyinstaller_command():
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onefile', '--name', 'hb-engine',
               '--collect-submodules', 'hb_engine',
               '--distpath', str(ROOT / 'dist'),
               '--workpath', str(ROOT / 'build' / 'pyinstaller'),
               '--specpath', str(ROOT / 'build')]
    for module in OPTIONAL_MODULES:
        if importlib.util.find_spec(module) is not None:
            command += ['--hidden-import', module]
    command.append(str(ROOT / 'dispatch.py'))
    return command


def _ipc_smoke(command, archive):
    """Exercise packaged engine modules over the real IPC protocol."""
    requests = [
        {'protocol_version': 1, 'request_id': 'advanced', 'method': 'search_advanced',
         'params': {'query': {'type': 'rule', 'kind': 'text', 'value': 'smokeword'},
                    'limit': 10}},
        {'protocol_version': 1, 'request_id': 'graph', 'method': 'relationships',
         'params': {}},
        {'protocol_version': 1, 'request_id': 'shutdown', 'method': 'shutdown',
         'params': {}},
    ]
    payload = '\n'.join(json.dumps(request) for request in requests) + '\n'
    completed = subprocess.run([*command, '--archive', str(archive), 'serve'],
                               input=payload, capture_output=True, text=True,
                               timeout=120)
    if completed.returncode != 0:
        raise SystemExit('engine IPC session failed: ' + completed.stderr)
    responses = {}
    for line in completed.stdout.splitlines():
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            raise SystemExit('engine IPC produced a non-JSON line: ' + line) from None
        if response.get('request_id'):
            responses[response['request_id']] = response
    for request_id in ('advanced', 'graph'):
        response = responses.get(request_id)
        if response is None:
            raise SystemExit(f'engine IPC returned no {request_id} response')
        if 'error' in response:
            raise SystemExit(f'engine IPC {request_id} failed: {response["error"]}')
    if responses['advanced']['result']['total'] < 2:
        raise SystemExit('search_advanced did not return both imported messages')
    if not responses['graph']['result']['edges']:
        raise SystemExit('relationships did not link the two message senders')
    return responses


def smoke(binary):
    """Exercise the built binary against a temporary archive."""
    command = [str(binary)]
    version = subprocess.run([*command, '--version'], capture_output=True,
                             text=True, check=True)
    if '0.3.0' not in version.stdout:
        raise SystemExit(f'unexpected --version output: {version.stdout!r}')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / 'smoke.eml'
        first.write_bytes(b'From: smoke@example.invalid\r\nSubject: Smoke\r\n'
                          b'Date: Mon, 01 Jan 2024 10:00:00 +0000\r\n'
                          b'Message-ID: <smoke-1@example.invalid>\r\n\r\nsmokeword')
        second = root / 'smoke-reply.eml'
        second.write_bytes(b'From: reply@example.invalid\r\nSubject: Re: Smoke\r\n'
                           b'Date: Mon, 01 Jan 2024 11:00:00 +0000\r\n'
                           b'Message-ID: <smoke-2@example.invalid>\r\n'
                           b'In-Reply-To: <smoke-1@example.invalid>\r\n\r\nsmokeword')
        archive = str(root / 'archive')
        subprocess.run([*command, '--archive', archive, 'import', str(first), str(second)],
                       check=True, capture_output=True)
        search = subprocess.run([*command, '--archive', archive, 'search', 'smokeword'],
                                check=True, capture_output=True, text=True)
        if 'Smoke' not in search.stdout:
            raise SystemExit(f'imported message not searchable: {search.stdout!r}')
        health = subprocess.run([*command, '--archive', archive, 'health'],
                                capture_output=True, text=True)
        if health.returncode != 0:
            raise SystemExit('health failed for the bundled engine: ' + health.stdout)
        _ipc_smoke(command, archive)
    print('bundled engine smoke test passed (CLI, search, health and IPC)')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--no-copy', action='store_true',
                        help='build only; do not copy into src-tauri/binaries')
    parser.add_argument('--smoke', action='store_true',
                        help='run the built binary against a temporary archive')
    parser.add_argument('--print-command', action='store_true',
                        help='print the PyInstaller command and exit')
    args = parser.parse_args(argv)
    command = pyinstaller_command()
    if args.print_command:
        print(' '.join(command))
        return 0
    if importlib.util.find_spec('PyInstaller') is None:
        raise SystemExit('PyInstaller is not installed: python3 -m pip install pyinstaller')
    subprocess.run(command, cwd=ROOT, check=True)
    built = ROOT / 'dist' / engine_name()
    if not built.is_file():
        raise SystemExit(f'expected {built} to be produced')
    if args.smoke:
        smoke(built)
    if args.no_copy:
        print(built)
        return 0
    destination = ROOT / 'src-tauri' / 'binaries' / external_bin_name(rust_target_triple())
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, destination)
    destination.chmod(0o755)
    print(f'copied {built} -> {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
