"""Cooperative IMAP synchronization lock on POSIX."""
from contextlib import contextmanager
import os

class SyncBusy(RuntimeError):
    pass

@contextmanager
def sync_lock(root):
    if os.name != 'posix':
        yield
        return
    import fcntl
    fd=os.open(root/'sync.lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise SyncBusy('Another synchronization is running') from None
        yield
    finally: os.close(fd)
