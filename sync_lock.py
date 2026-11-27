# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Cooperative cross-platform write lock for an archive directory.

Only one process may perform an archive-mutating operation (ingest, sync,
migration, reindex, recovery, backup or restore) at a time. The lock is an
operating-system advisory lock on `sync.lock`, so it is released when the
owning process exits, including after a crash; a stale lock file is harmless
and is reused on the next run.

POSIX uses `flock`; Windows uses `msvcrt.locking` on a single byte. Both are
non-blocking, and contention raises `SyncBusy` rather than waiting.
"""
from contextlib import contextmanager
import os

LOCK_SUPPORTED = os.name in ('posix', 'nt')

class SyncBusy(RuntimeError):
    pass

def _acquire(fd):
    """Try to take an exclusive, non-blocking lock on `fd`."""
    if os.name == 'nt':
        import msvcrt
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SyncBusy('Another archive operation is running') from None
    elif os.name == 'posix':
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SyncBusy('Another archive operation is running') from None
    else:
        raise RuntimeError(f'Archive locking is not supported on {os.name!r}')

def _release(fd):
    if os.name == 'nt':
        import msvcrt
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    elif os.name == 'posix':
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass

@contextmanager
def file_lock(path):
    """Hold an exclusive, non-blocking lock on `path` for the block."""
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_CLOEXEC', 0)
    fd = os.open(os.fspath(path), flags, 0o600)
    try:
        _acquire(fd)
        try:
            yield
        finally:
            _release(fd)
    finally:
        os.close(fd)

@contextmanager
def sync_lock(root):
    """Hold the exclusive archive write lock for the duration of the block."""
    with file_lock(os.path.join(os.fspath(root), 'sync.lock')):
        yield
