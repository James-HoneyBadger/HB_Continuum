# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Offline importer for user-obtained Facebook JSON exports.

No scraping, no credentials, no unofficial APIs. The importer reads JSON the
user already exported, preserves each record's original JSON and the source
file's SHA-256, and writes normalized records into the source-independent
catalog database. Original export files are never modified or uploaded.
"""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from catalog import Catalog

SUPPORTED = ('posts', 'comments', 'messages', 'events', 'media', 'reactions')

# category -> list keys encountered in real exports; order is the match order.
LIST_KEYS = {
    'posts': ('your_posts', 'posts', 'your_posts_in_groups', 'group_posts'),
    'comments': ('comments', 'your_comments_in_groups', 'group_comments'),
    'messages': ('messages',),
    'events': ('your_events', 'events', 'event_responses'),
    'reactions': ('reactions', 'reactions_v2'),
}

class FacebookParseError(ValueError):
    pass

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def _expand(paths):
    files = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for child in sorted(path.rglob('*.json')):
                relative = child.relative_to(path)
                if any(part.startswith('.') for part in relative.parts):
                    continue
                files.append(child)
    return list(dict.fromkeys(files))

def _read_json(path):
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FacebookParseError(f'{path}: not parseable JSON/UTF-8 ({exc})') from None
    return raw, doc

def _extract_items(path, doc):
    name = path.name.lower()
    if isinstance(doc, dict):
        for category, keys in LIST_KEYS.items():
            for key in keys:
                if isinstance(doc.get(key), list):
                    return category, key, doc[key]
        for key in ('videos', 'photos', 'your_videos', 'your_photos'):
            if isinstance(doc.get(key), list):
                return 'media', key, doc[key]
        return 'unknown', None, []
    if isinstance(doc, list):
        if 'comment' in name:
            return 'comments', 'comments', doc
        if 'video' in name or 'photo' in name:
            return 'media', 'media', doc
        if 'reaction' in name or 'like' in name:
            return 'reactions', 'reactions', doc
        return 'posts', 'posts', doc
    return 'unknown', None, []

def _norm_time(item, keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                continue
        if isinstance(value, (int, float)):
            seconds = value / 1000.0 if key == 'timestamp_ms' else value
            try:
                precision = 'ms' if key == 'timestamp_ms' else 'second'
                return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(), precision
            except (OverflowError, OSError, ValueError):
                return None, 'unknown'
    return None, 'unknown'

def _body_posts(item):
    parts = []
    title = item.get('title')
    if isinstance(title, str) and title.strip():
        parts.append(title.strip())
    for d in item.get('data') or []:
        if isinstance(d, dict):
            post = d.get('post')
            if isinstance(post, str) and post.strip():
                parts.append(post.strip())
    return '\n'.join(parts)

def _body_comments(item):
    parts = []
    for d in item.get('data') or []:
        if isinstance(d, dict):
            comment = d.get('comment')
            if isinstance(comment, dict) and isinstance(comment.get('comment'), str) and comment['comment'].strip():
                parts.append(comment['comment'].strip())
    return '\n'.join(parts)

def _media_body(item):
    parts = []
    title = item.get('title')
    if isinstance(title, str) and title.strip():
        parts.append(title.strip())
    description = item.get('description')
    if isinstance(description, str) and description.strip():
        parts.append(description.strip())
    metadata = item.get('media_metadata')
    if isinstance(metadata, dict):
        metadata_title = metadata.get('title')
        if isinstance(metadata_title, str) and metadata_title.strip():
            parts.append(metadata_title.strip())
    return '\n'.join(parts)

def _reaction_body(item):
    parts = []
    title = item.get('title')
    if isinstance(title, str) and title.strip():
        parts.append('Reaction to: ' + title.strip())
    for d in item.get('data') or []:
        if isinstance(d, dict):
            reaction = d.get('reaction')
            if isinstance(reaction, dict) and isinstance(reaction.get('reaction'), str) and reaction['reaction'].strip():
                parts.append(reaction['reaction'].strip())
    return '\n'.join(parts)

def _reaction_actor(item):
    for d in item.get('data') or []:
        if isinstance(d, dict):
            reaction = d.get('reaction')
            if isinstance(reaction, dict) and isinstance(reaction.get('actor'), str):
                return reaction['actor']
    return None

def _normalize(category, item):
    if not isinstance(item, dict):
        return None
    if category == 'messages':
        occurred, precision = _norm_time(item, ('timestamp_ms',))
    elif category == 'events':
        occurred, precision = _norm_time(item, ('start_timestamp', 'timestamp'))
    elif category == 'media':
        occurred, precision = _norm_time(item, ('creation_timestamp', 'timestamp'))
    else:
        occurred, precision = _norm_time(item, ('timestamp',))
    if category == 'posts':
        return {'record_kind': 'post', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _body_posts(item), 'original': item}
    if category == 'comments':
        return {'record_kind': 'comment', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _body_comments(item), 'original': item}
    if category == 'messages':
        actor = item.get('sender_name') if isinstance(item.get('sender_name'), str) else None
        body = item.get('content') if isinstance(item.get('content'), str) else ''
        return {'record_kind': 'message', 'actor': actor, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': body, 'original': item}
    if category == 'events':
        name = item.get('name') if isinstance(item.get('name'), str) else ''
        description = item.get('description') if isinstance(item.get('description'), str) else ''
        body = '\n'.join(x for x in (name, description) if x.strip())
        return {'record_kind': 'event', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': body, 'original': item}
    if category == 'media':
        return {'record_kind': 'media', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _media_body(item), 'original': item}
    if category == 'reactions':
        return {'record_kind': 'reaction', 'actor': _reaction_actor(item), 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _reaction_body(item), 'original': item}
    return None

def _record_id(source_key, original):
    canonical = json.dumps(original, sort_keys=True, ensure_ascii=False)
    return sha256((source_key + '\0' + canonical).encode('utf-8'))

def _source_key(path, category, key, doc):
    if category == 'messages':
        title = doc.get('title')
        if isinstance(title, str) and title.strip():
            return title.strip()
        return path.parent.name or key
    return key

def preview(paths, root=None):
    files = _expand(paths)
    result = {'files_discovered': len(files), 'files': [],
              'estimated_records': 0, 'supported_records': 0,
              'unsupported_records': 0, 'warnings': []}
    for path in files:
        try:
            raw, doc = _read_json(path)
        except FacebookParseError as exc:
            result['warnings'].append(str(exc))
            continue
        category, key, items = _extract_items(path, doc)
        estimated = len(items)
        supported = category in SUPPORTED
        result['files'].append({'path': str(path), 'category': category,
                                'size': len(raw), 'estimated_records': estimated,
                                'supported': supported})
        result['estimated_records'] += estimated
        if supported:
            result['supported_records'] += estimated
        else:
            result['unsupported_records'] += estimated
    return result

def import_files(paths, root, progress=None, cancel_event=None):
    files = _expand(paths)
    catalog = Catalog(root)
    counts = {'files_discovered': len(files), 'files_imported': 0, 'files_skipped': 0,
              'files_unsupported': 0, 'records_encountered': 0, 'records_imported': 0,
              'records_duplicate': 0, 'records_unsupported': 0,
              'parse_errors': 0, 'cancelled': False, 'warnings': []}
    total = len(files)
    try:
        for done, path in enumerate(files, 1):
            if cancel_event is not None and cancel_event.is_set():
                counts['cancelled'] = True
                break
            try:
                raw, doc = _read_json(path)
            except FacebookParseError as exc:
                counts['parse_errors'] += 1
                counts['warnings'].append(str(exc))
                if progress is not None: progress(done, total, str(path), 'error')
                continue
            category, key, items = _extract_items(path, doc)
            file_hash = sha256(raw)
            if catalog.has_file(file_hash):
                counts['files_skipped'] += 1
                if progress is not None: progress(done, total, str(path), 'skipped')
                continue
            if category not in SUPPORTED:
                counts['files_unsupported'] += 1
                counts['warnings'].append(f'{path}: unsupported category {category!r}')
                if progress is not None: progress(done, total, str(path), 'unsupported')
                continue
            source_key = _source_key(path, category, key, doc)
            records = [r for r in (_normalize(category, item) for item in items) if r is not None]
            counts['records_encountered'] += len(items)
            counts['records_unsupported'] += len(items) - len(records)
            with catalog.db:
                catalog.add_file(file_hash, 'facebook', source_key, str(path), len(raw), utcnow())
                for record in records:
                    record_id = _record_id(source_key, record['original'])
                    inserted = catalog.add_record(
                        record_id, 'facebook', source_key, record['record_kind'],
                        record['actor'], record['occurred_at'], record['occurred_precision'],
                        record['body'], json.dumps(record['original'], ensure_ascii=False),
                        file_hash, utcnow())
                    if inserted:
                        counts['records_imported'] += 1
                    else:
                        counts['records_duplicate'] += 1
            counts['files_imported'] += 1
            if progress is not None: progress(done, total, str(path), 'imported')
        return counts
    finally:
        catalog.close()
