# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Streaming MBOX import with explicit provenance.

MBOX is a container, not a byte-preserving archive. A message extracted from an
MBOX file is reconstructed from its headers and body, so the stored ``raw/``
bytes are a faithful re-serialisation rather than the original octets of
whatever wrote the file. Every imported message is recorded with
``account='mbox:<file>'`` and ``folder='mbox'`` so reconstructed records are
never confused with original EML imports or IMAP retrievals.

The source file is opened read-only and never modified. Because each message is
hashed and stored independently, an interrupted run leaves a consistent archive
and re-running the same file skips what is already present.
"""

import hashlib
import mailbox
from pathlib import Path

from .timestamps import parse_timestamp

MAX_MESSAGE_BYTES = 64 * 1024 * 1024


class MboxError(ValueError):
    """The file cannot be read as an MBOX mailbox."""


def _open(path):
    source = Path(path).expanduser()
    if source.is_symlink():
        raise MboxError(f'refusing symbolic link: {source}')
    if not source.is_file():
        raise MboxError(f'not a readable MBOX file: {source}')
    try:
        return mailbox.mbox(str(source), factory=None, create=False)
    except (OSError, mailbox.Error) as exc:
        raise MboxError(f'cannot open {source.name}: {exc}') from None


def iter_messages(path):
    """Yield ``(index, raw_bytes, error)`` for each message, one at a time."""
    box = _open(path)
    try:
        for index, key in enumerate(box.keys()):
            try:
                message = box.get_message(key)
            except Exception as exc:  # mailbox raises various types
                yield index, None, f'{type(exc).__name__}: {exc}'
                continue
            if message is None:
                yield index, None, 'empty message'
                continue
            try:
                raw = message.as_bytes(unixfrom=False)
            except Exception as exc:
                yield index, None, f'{type(exc).__name__}: {exc}'
                continue
            if len(raw) > MAX_MESSAGE_BYTES:
                yield index, None, 'message exceeds the 64 MiB limit'
                continue
            yield index, raw, None
    finally:
        box.close()


def _subject(raw):
    try:
        import email
        return str(email.message_from_bytes(raw).get('Subject', ''))
    except Exception:
        return ''


def preview(path):
    """Describe an MBOX file without importing it."""
    source = Path(path).expanduser()
    counts = {'messages': 0, 'malformed': 0, 'duplicate_hashes': 0}
    dates = []
    seen = set()
    problems = []
    for index, raw, error in iter_messages(path):
        counts['messages'] += 1
        if error:
            counts['malformed'] += 1
            problems.append({'index': index, 'error': error})
            continue
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            counts['duplicate_hashes'] += 1
        seen.add(digest)
        try:
            import email
            header = str(email.message_from_bytes(raw).get('Date', ''))
            stamp = parse_timestamp(header)[0]
        except Exception:
            stamp = None
        if stamp:
            dates.append(stamp)
    return {
        'source': str(source),
        'name': source.name,
        'size': source.stat().st_size if source.is_file() else 0,
        'messages': counts['messages'],
        'malformed': counts['malformed'],
        'duplicate_messages': counts['duplicate_hashes'],
        'date_first': min(dates) if dates else None,
        'date_last': max(dates) if dates else None,
        'problems': problems[:20],
        'note': 'Extracted messages are reconstructed from the container; '
                'they are not byte-identical to the original EML.',
    }


def import_mbox(archive, path, progress=None, cancel_event=None):
    """Import every message in an MBOX file into ``archive``.

    Returns counts plus per-message errors. ``cancel_event`` is any object with
    an ``is_set()`` method; cancelling leaves already-imported messages stored.
    """
    source = Path(path).expanduser()
    account = f'mbox:{source.name}'
    result = {'source': str(source), 'imported': 0, 'existing': 0,
              'failed': 0, 'cancelled': False, 'errors': []}
    for index, raw, error in iter_messages(path):
        if cancel_event is not None and cancel_event.is_set():
            result['cancelled'] = True
            break
        if error:
            result['failed'] += 1
            result['errors'].append({'index': index, 'error': error})
            continue
        try:
            digest = hashlib.sha256(raw).hexdigest()
            row = archive.db.execute('SELECT 1 FROM messages WHERE hash=?',
                                     (digest,)).fetchone()
            archive.ingest(raw, (account, 'mbox', '', str(index)))
            if row:
                result['existing'] += 1
            else:
                result['imported'] += 1
        except Exception as exc:
            result['failed'] += 1
            result['errors'].append({'index': index,
                                     'error': f'{type(exc).__name__}: {exc}'})
        if progress is not None:
            progress(index + 1, result['imported'], result['existing'],
                     result['failed'])
    return result
