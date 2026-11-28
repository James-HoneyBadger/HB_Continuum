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
from .catalog import Catalog
from .migrations import attachment_search_text

SUPPORTED = ('posts', 'comments', 'messages', 'events', 'media', 'reactions')
MAX_ATTACHMENTS = 100
MAX_ATTACHMENT_TEXT = 2000

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

def _normalize(category, item, source_key=''):
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
    meta = _record_metadata(category, source_key, item, occurred)
    if category == 'posts':
        return {'record_kind': 'post', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _body_posts(item),
                'original': item, **meta}
    if category == 'comments':
        return {'record_kind': 'comment', 'actor': _comment_actor(item),
                'occurred_at': occurred, 'occurred_precision': precision,
                'body': _body_comments(item), 'original': item, **meta}
    if category == 'messages':
        actor = item.get('sender_name') if isinstance(item.get('sender_name'), str) else None
        body = item.get('content') if isinstance(item.get('content'), str) else ''
        return {'record_kind': 'message', 'actor': actor, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': body,
                'original': item, **meta}
    if category == 'events':
        name = item.get('name') if isinstance(item.get('name'), str) else ''
        description = item.get('description') if isinstance(item.get('description'), str) else ''
        body = '\n'.join(x for x in (name, description) if x.strip())
        return {'record_kind': 'event', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': body,
                'original': item, **meta}
    if category == 'media':
        return {'record_kind': 'media', 'actor': None, 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _media_body(item),
                'original': item, **meta}
    if category == 'reactions':
        return {'record_kind': 'reaction', 'actor': _reaction_actor(item), 'occurred_at': occurred,
                'occurred_precision': precision, 'body': _reaction_body(item),
                'original': item, **meta}
    return None

def _clean_text(value):
    if isinstance(value, str):
        value = value.strip()
        return value[:MAX_ATTACHMENT_TEXT] or None
    return None

def _epoch(value, milliseconds=False):
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    try:
        return value / 1000.0 if milliseconds else value
    except OverflowError:
        return None

def _iso_time(value, milliseconds=False):
    seconds = _epoch(value, milliseconds)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None

def _attachment_time(value):
    return _iso_time(value)

def _media_attachment(media, kind='media'):
    if not isinstance(media, dict):
        return None
    entry = {'kind': kind}
    name = _clean_text(media.get('title'))
    if name:
        entry['name'] = name
    uri = _clean_text(media.get('uri'))
    if uri:
        entry['uri'] = uri
    description = _clean_text(media.get('description'))
    if description:
        entry['description'] = description
    created = _attachment_time(media.get('creation_timestamp'))
    if created:
        entry['created_at'] = created
    thumbnail = media.get('thumbnail')
    if isinstance(thumbnail, dict):
        thumb_uri = _clean_text(thumbnail.get('uri'))
        if thumb_uri:
            entry['thumbnail'] = thumb_uri
    metadata = media.get('media_metadata')
    if isinstance(metadata, dict):
        if 'video_metadata' in metadata:
            entry['kind'] = 'video'
        elif 'photo_metadata' in metadata:
            entry['kind'] = 'photo'
    return entry if len(entry) > 1 else None

def _post_attachments(item):
    values = item.get('attachments')
    if isinstance(values, dict):
        values = [values]
    entries = []
    for attachment in values or []:
        if not isinstance(attachment, dict):
            continue
        data = attachment.get('data')
        if isinstance(data, dict):
            data = [data]
        for entry in data or []:
            if not isinstance(entry, dict):
                continue
            media = entry.get('media')
            normalized = _media_attachment(media)
            if normalized:
                entries.append(normalized)
            external = entry.get('external_context')
            if isinstance(external, dict):
                link = {'kind': 'external_link'}
                name = _clean_text(external.get('name'))
                source = _clean_text(external.get('source'))
                url = _clean_text(external.get('url'))
                if name:
                    link['name'] = name
                if source:
                    link['source'] = source
                if url:
                    link['url'] = url
                if len(link) > 1:
                    entries.append(link)
            place = entry.get('place')
            if isinstance(place, dict):
                location = {'kind': 'place'}
                name = _clean_text(place.get('name'))
                address = _clean_text(place.get('address'))
                if name:
                    location['name'] = name
                if address:
                    location['address'] = address
                coordinates = place.get('coordinate')
                if isinstance(coordinates, dict):
                    latitude = coordinates.get('latitude')
                    longitude = coordinates.get('longitude')
                    if isinstance(latitude, (int, float)) and not isinstance(latitude, bool):
                        location['latitude'] = latitude
                    if isinstance(longitude, (int, float)) and not isinstance(longitude, bool):
                        location['longitude'] = longitude
                if len(location) > 1:
                    entries.append(location)
            event = entry.get('event')
            if isinstance(event, dict):
                occurrence = {'kind': 'event'}
                name = _clean_text(event.get('name'))
                if name:
                    occurrence['name'] = name
                start = _iso_time(event.get('start_timestamp'))
                end = _iso_time(event.get('end_timestamp'))
                if start:
                    occurrence['start_at'] = start
                if end:
                    occurrence['end_at'] = end
                if len(occurrence) > 1:
                    entries.append(occurrence)
            for_sale = entry.get('for_sale_item')
            if isinstance(for_sale, dict):
                sale = {'kind': 'marketplace'}
                title = _clean_text(for_sale.get('title'))
                price = _clean_text(for_sale.get('price'))
                seller = _clean_text(for_sale.get('seller'))
                if title:
                    sale['name'] = title
                if price:
                    sale['price'] = price
                if seller:
                    sale['seller'] = seller
                if len(sale) > 1:
                    entries.append(sale)
    return _trim_attachments(entries)

def _message_attachments(item):
    entries = []
    for key, kind in (('photos', 'photo'), ('videos', 'video'),
                      ('audio_files', 'audio'), ('files', 'file'), ('gifs', 'gif')):
        values = item.get(key)
        if isinstance(values, dict):
            values = [values]
        for value in values or []:
            if not isinstance(value, dict):
                continue
            entry = {'kind': kind}
            uri = _clean_text(value.get('uri'))
            if uri:
                entry['uri'] = uri
            name = _clean_text(value.get('name'))
            if name:
                entry['name'] = name
            created = _attachment_time(value.get('creation_timestamp'))
            if created:
                entry['created_at'] = created
            thumbnail = value.get('thumbnail')
            if isinstance(thumbnail, dict):
                thumb_uri = _clean_text(thumbnail.get('uri'))
                if thumb_uri:
                    entry['thumbnail'] = thumb_uri
            if len(entry) > 1:
                entries.append(entry)
    sticker = item.get('sticker')
    if isinstance(sticker, dict):
        uri = _clean_text(sticker.get('uri'))
        if uri:
            entries.append({'kind': 'sticker', 'uri': uri})
    share = item.get('share')
    if isinstance(share, dict):
        entry = {'kind': 'share'}
        for field, label in (('link', 'url'), ('title', 'name'),
                             ('source', 'source'), ('description', 'description')):
            value = _clean_text(share.get(field))
            if value:
                entry[label] = value
        if len(entry) > 1:
            entries.append(entry)
    reactions = item.get('reactions')
    if isinstance(reactions, dict):
        reactions = [reactions]
    for reaction in reactions or []:
        if not isinstance(reaction, dict):
            continue
        entry = {'kind': 'reaction'}
        value = _clean_text(reaction.get('reaction'))
        actor = _clean_text(reaction.get('actor'))
        if value:
            entry['reaction'] = value
        if actor:
            entry['actor'] = actor
        if len(entry) > 1:
            entries.append(entry)
    return _trim_attachments(entries)

def _trim_attachments(entries):
    seen = set()
    result = []
    for entry in entries:
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
        if len(result) >= MAX_ATTACHMENTS:
            break
    return result

def _attachments(category, item):
    if category in ('posts', 'comments'):
        return _post_attachments(item)
    if category == 'messages':
        return _message_attachments(item)
    return []

def _comment_actor(item):
    for entry in item.get('data') or []:
        if isinstance(entry, dict):
            comment = entry.get('comment')
            if isinstance(comment, dict):
                actor = _clean_text(comment.get('author'))
                if actor:
                    return actor
    return None

def _update_time(item):
    candidates = []
    for entry in item.get('data') or []:
        if not isinstance(entry, dict):
            continue
        objects = [entry]
        comment = entry.get('comment')
        if isinstance(comment, dict):
            objects.append(comment)
        for obj in objects:
            for key, milliseconds in (('update_timestamp', False),
                                      ('update_timestamp_ms', True),
                                      ('updated_timestamp', False),
                                      ('edited_timestamp', False)):
                seconds = _epoch(obj.get(key), milliseconds)
                if seconds is not None:
                    candidates.append(seconds)
    if not candidates:
        return None
    try:
        return datetime.fromtimestamp(max(candidates), tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None

def _revision_key(category, source_key, item, occurred):
    if category == 'posts':
        return f'post|{source_key}|{occurred}' if occurred else None
    if category == 'comments':
        comment = None
        for entry in item.get('data') or []:
            if isinstance(entry, dict) and isinstance(entry.get('comment'), dict):
                comment = entry['comment']
                break
        if not comment:
            return None
        stamp = comment.get('timestamp') or item.get('timestamp')
        author = _clean_text(comment.get('author')) or ''
        return f'comment|{source_key}|{stamp}|{author}' if stamp is not None else None
    return None

def _record_metadata(category, source_key, item, occurred):
    updated = _update_time(item)
    revision_kind = None
    if updated and category == 'posts':
        revision_kind = 'post_update'
    elif updated and category == 'comments':
        revision_kind = 'comment_update'
    return {'updated_at': updated, 'revision_kind': revision_kind,
            'revision_key': _revision_key(category, source_key, item, occurred),
            'attachments': _attachments(category, item)}

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
              'records_revised': 0, 'attachments_indexed': 0,
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
            records = [r for r in (_normalize(category, item, source_key)
                                   for item in items) if r is not None]
            counts['records_encountered'] += len(items)
            counts['records_unsupported'] += len(items) - len(records)
            with catalog.db:
                catalog.add_file(file_hash, 'facebook', source_key, str(path), len(raw), utcnow())
                for record in records:
                    record_id = _record_id(source_key, record['original'])
                    revision_key = record['revision_key']
                    revision_index = None
                    if revision_key:
                        revision_index = catalog.db.execute(
                            'SELECT count(*) FROM records WHERE revision_key=?',
                            (revision_key,)).fetchone()[0] + 1
                    attachments_text = attachment_search_text(record['attachments'])
                    inserted = catalog.add_record(
                        record_id, 'facebook', source_key, record['record_kind'],
                        record['actor'], record['occurred_at'], record['occurred_precision'],
                        record['body'], json.dumps(record['original'], ensure_ascii=False),
                        file_hash, utcnow(), updated_at=record['updated_at'],
                        revision_kind=record['revision_kind'],
                        revision_key=revision_key, revision_index=revision_index,
                        attachments_json=json.dumps(record['attachments'],
                                                    ensure_ascii=False),
                        attachments_text=attachments_text)
                    if inserted:
                        counts['records_imported'] += 1
                        if record['updated_at']:
                            counts['records_revised'] += 1
                        counts['attachments_indexed'] += len(record['attachments'])
                    else:
                        counts['records_duplicate'] += 1
            counts['files_imported'] += 1
            if progress is not None: progress(done, total, str(path), 'imported')
        return counts
    finally:
        catalog.close()
