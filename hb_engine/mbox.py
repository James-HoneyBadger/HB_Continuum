# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Streaming MBOX import with explicit, collision-free provenance.

MBOX is a container, not a byte-preserving archive. A message extracted from an
MBOX file is reconstructed from its headers and body, so the stored ``raw/``
bytes are a faithful re-serialisation rather than the original octets of
whatever wrote the file.

Provenance identifies both the file name and a digest of the file contents, so
two different exports called ``Inbox.mbox`` - or a later export at the same
path - cannot collide, while re-importing an unchanged file stays idempotent.

The source file is opened read-only and never modified. Each message is hashed
and stored independently, so an interrupted run leaves a consistent archive.
"""

import email
import hashlib
import mailbox
from pathlib import Path

from .timestamps import parse_timestamp

MAX_MESSAGE_BYTES = 64 * 1024 * 1024


class MboxError(ValueError):
    """The file cannot be read as an MBOX mailbox."""


def _source(path):
    source = Path(path).expanduser()
    if source.is_symlink():
        raise MboxError(f'refusing symbolic link: {source}')
    if not source.is_file():
        raise MboxError(f'not a readable MBOX file: {source}')
    return source


def file_digest(path):
    """SHA-256 of the container file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_account(path):
    """Provenance account for *path*, stable for identical content."""
    source = _source(path)
    return f'mbox:{source.name}#{file_digest(source)[:16]}', source


def _message_warnings(message):
    warnings = []
    for defect in getattr(message, 'defects', []) or []:
        warnings.append(f'header defect: {defect}')
    try:
        for part in message.walk():
            for defect in getattr(part, 'defects', []) or []:
                warnings.append(f'mime defect: {defect}')
    except Exception as exc:
        warnings.append(f'unreadable mime structure: {type(exc).__name__}: {exc}')
    return warnings


def iter_messages(path):
    """Yield ``(index, raw_bytes, error, warnings)`` one message at a time."""
    try:
        box = mailbox.mbox(str(_source(path)), factory=None, create=False)
    except (OSError, mailbox.Error) as exc:
        raise MboxError(f'cannot open {Path(path).name}: {exc}') from None
    try:
        for index, key in enumerate(box.keys()):
            try:
                message = box.get_message(key)
            except Exception as exc:  # mailbox raises several unrelated types
                yield index, None, f'{type(exc).__name__}: {exc}', []
                continue
            if message is None:
                yield index, None, 'empty message', []
                continue
            warnings = _message_warnings(message)
            try:
                raw = message.as_bytes(unixfrom=False)
            except Exception as exc:
                yield index, None, f'{type(exc).__name__}: {exc}', warnings
                continue
            if len(raw) > MAX_MESSAGE_BYTES:
                yield index, None, 'message exceeds the 64 MiB limit', warnings
                continue
            yield index, raw, None, warnings
    finally:
        box.close()


def preview(path):
    """Describe an MBOX file without importing it."""
    source = _source(path)
    counts = {'messages': 0, 'malformed': 0, 'duplicate_messages': 0}
    dates = []
    seen = set()
    problems = []
    warnings = []
    for index, raw, error, message_warnings in iter_messages(source):
        counts['messages'] += 1
        if error:
            counts['malformed'] += 1
            problems.append({'index': index, 'error': error})
            continue
        for warning in message_warnings:
            warnings.append({'index': index, 'warning': warning})
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            counts['duplicate_messages'] += 1
        seen.add(digest)
        try:
            stamp = parse_timestamp(str(email.message_from_bytes(raw).get('Date', '')))[0]
        except Exception:
            stamp = None
        if stamp:
            dates.append(stamp)
    return {
        'source': str(source),
        'name': source.name,
        'content_digest': file_digest(source),
        'size': source.stat().st_size,
        'messages': counts['messages'],
        'malformed': counts['malformed'],
        'duplicate_messages': counts['duplicate_messages'],
        'date_first': min(dates) if dates else None,
        'date_last': max(dates) if dates else None,
        'problems': problems[:20],
        'warnings': warnings[:20],
        'note': 'Extracted messages are reconstructed from the container; '
                'they are not byte-identical to the original EML.',
    }


def import_mbox(archive, path, progress=None, cancel_event=None):
    """Import every message in an MBOX file into ``archive``.

    Returns counts, per-message errors and parser warnings. ``cancel_event`` is
    any object with ``is_set()``; cancelling keeps what was already imported.
    """
    account, source = source_account(path)
    result = {'source': str(source), 'account': account, 'imported': 0,
              'existing': 0, 'failed': 0, 'cancelled': False,
              'errors': [], 'warnings': []}
    done = 0
    for index, raw, error, message_warnings in iter_messages(source):
        done = index + 1
        if cancel_event is not None and cancel_event.is_set():
            result['cancelled'] = True
            break
        for warning in message_warnings:
            result['warnings'].append({'index': index, 'warning': warning})
        if error:
            result['failed'] += 1
            result['errors'].append({'index': index, 'error': error})
        else:
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
            progress(done, result['imported'], result['existing'], result['failed'])
    return result
