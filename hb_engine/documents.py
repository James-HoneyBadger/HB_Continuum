# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local document ingestion into the source-independent catalog.

Plain text, Markdown, CSV and JSON use built-in UTF-8 extraction. PDF and
DOCX text extraction use optional local libraries when installed; without them
the file is reported as unsupported rather than silently indexed as empty.
Original files are hashed and referenced, never copied, uploaded or modified.
"""
import hashlib, importlib.util, io, json, os
from datetime import datetime, timezone
from pathlib import Path

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 5_000_000
MAX_PAGES = 1_000
TEXT_EXTENSIONS = {'.txt': 'text', '.md': 'markdown', '.markdown': 'markdown',
                   '.csv': 'csv', '.json': 'json', '.pdf': 'pdf', '.docx': 'docx'}
SUPPORTED = frozenset(TEXT_EXTENSIONS)
BUILTIN = frozenset(('.txt', '.md', '.markdown', '.csv', '.json'))


class DocumentError(ValueError):
    pass


class ExtractionUnavailable(DocumentError):
    pass


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


def _iso_from_mtime(path):
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None, 'unknown'
    try:
        return datetime.fromtimestamp(stamp, timezone.utc).isoformat(), 'second'
    except (OverflowError, OSError, ValueError):
        return None, 'unknown'


def _expand(paths):
    """Return (path, source label) pairs; directories are walked recursively."""
    files = []
    warnings = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_symlink():
            warnings.append(f'{path}: symbolic links are not imported')
            continue
        if path.is_dir():
            for child in sorted(path.rglob('*')):
                if child.name.startswith('.') or any(part.startswith('.')
                                                     for part in child.relative_to(path).parts):
                    continue
                if child.is_symlink():
                    warnings.append(f'{child}: symbolic links are not imported')
                    continue
                if child.is_file():
                    files.append((child, child.relative_to(path).as_posix()))
        elif path.is_file():
            files.append((path, path.name))
        else:
            warnings.append(f'{path}: not found')
    return list(dict.fromkeys(files)), warnings


def extractor_name(extension):
    extension = extension.lower()
    if extension in BUILTIN:
        return 'builtin'
    if extension == '.pdf':
        return 'pypdf' if importlib.util.find_spec('pypdf') is not None else None
    if extension == '.docx':
        return 'python-docx' if importlib.util.find_spec('docx') is not None else None
    return None


def _text_from_bytes(raw):
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        try:
            return raw.decode('utf-16')
        except UnicodeDecodeError:
            raise DocumentError('document is not valid UTF-16 text') from None
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DocumentError('document is not valid UTF-8 text') from None


def _extract_text(extension, raw):
    text = _text_from_bytes(raw)
    if extension == '.json':
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise DocumentError(f'invalid JSON: {exc.msg} at line {exc.lineno}') from None
    return text, [], 'builtin'


def _extract_pdf(raw):
    try:
        import pypdf
    except ImportError:
        raise ExtractionUnavailable(
            'PDF text extraction requires the optional pypdf package') from None
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise DocumentError(f'PDF could not be opened: {type(exc).__name__}') from None
    parts = []
    pages = []
    for number, page in enumerate(reader.pages, 1):
        if number > MAX_PAGES:
            break
        try:
            text = page.extract_text() or ''
        except Exception as exc:
            raise DocumentError(f'PDF page {number} could not be extracted: '
                                f'{type(exc).__name__}') from None
        if text.strip():
            pages.append({'kind': 'page', 'page': number,
                          'characters': len(text)})
        parts.append(text)
    return '\n\n'.join(parts), pages, 'pypdf'


def _extract_docx(raw):
    try:
        import docx
    except ImportError:
        raise ExtractionUnavailable(
            'DOCX text extraction requires the optional python-docx package') from None
    try:
        document = docx.Document(io.BytesIO(raw))
    except Exception as exc:
        raise DocumentError(f'DOCX could not be opened: {type(exc).__name__}') from None
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(' | '.join(cell.text for cell in row.cells))
    return '\n'.join(parts), [], 'python-docx'


def extract_attachment_text(filename, raw, mime_type=None):
    """Best-effort text from an email attachment; returns '' when unavailable.

    Only PDF and DOCX need this path: text attachments are decoded directly by
    the MIME indexer. Failures are contained so one malformed attachment can
    never reject an otherwise valid message.
    """
    extension = Path(str(filename or '')).suffix.lower()
    kinds = {str(mime_type or '').lower()}
    is_pdf = extension == '.pdf' or 'application/pdf' in kinds
    is_docx = extension == '.docx' or any('wordprocessingml' in kind for kind in kinds)
    if not (is_pdf or is_docx):
        return ''
    if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
        return ''
    try:
        text = _extract_pdf(raw)[0] if is_pdf else _extract_docx(raw)[0]
    except DocumentError:
        return ''
    return text[:MAX_TEXT_CHARS]


def extract_document(path):
    """Extract text and page references; never executes document content."""
    path = Path(path)
    extension = path.suffix.lower()
    if extension not in SUPPORTED:
        raise DocumentError(f'unsupported document type {extension or "(none)"}')
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise DocumentError(
            f'file is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit')
    if extension in BUILTIN:
        text, pages, extractor = _extract_text(extension, raw)
    elif extension == '.pdf':
        text, pages, extractor = _extract_pdf(raw)
    else:
        text, pages, extractor = _extract_docx(raw)
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS]
    if not text.strip():
        raise DocumentError(
            'no extractable text; scanned images and OCR are not supported')
    return {'text': text, 'pages': pages, 'extractor': extractor,
            'truncated': truncated, 'raw': raw}


def preview(paths):
    files, warnings = _expand(paths)
    result = {'files_discovered': len(files), 'files': [],
              'supported_files': 0, 'unsupported_files': 0,
              'warnings': warnings, 'extractor_warnings': []}
    for path, label in files:
        extension = path.suffix.lower()
        size = path.stat().st_size
        supported = extension in SUPPORTED and size <= MAX_FILE_BYTES
        extractor = extractor_name(extension) if extension in SUPPORTED else None
        result['files'].append({
            'path': str(path), 'label': label, 'extension': extension,
            'size': size, 'supported': supported, 'extractor': extractor,
        })
        if supported:
            result['supported_files'] += 1
        else:
            result['unsupported_files'] += 1
        if extension in SUPPORTED and extractor is None:
            result['extractor_warnings'].append(
                f'{path.name}: {extension} extraction needs an optional local package')
    return result


def _document_metadata(path, label, extension, size, digest, extracted, occurred, precision):
    return {
        'path': str(path), 'label': label, 'filename': path.name,
        'extension': extension, 'size': size, 'sha256': digest,
        'extractor': extracted['extractor'], 'pages': extracted['pages'],
        'truncated': extracted['truncated'],
        'occurred_at': occurred, 'occurred_precision': precision,
        'limitations': [
            'Original document bytes are referenced by hash and path, not copied.',
            'Only extracted text is searchable; images, layout and formatting are not preserved.',
            'Scanned PDFs without a text layer are not OCRed.',
        ],
    }


def import_files(paths, root, progress=None, cancel_event=None):
    from .catalog import Catalog
    from .dispatch import Archive
    files, warnings = _expand(paths)
    catalog = Catalog(root)
    archive = Archive(root)
    counts = {
        'files_discovered': len(files), 'files_imported': 0, 'files_skipped': 0,
        'files_unsupported': 0, 'records_imported': 0, 'records_duplicate': 0,
        'extraction_failures': 0, 'characters_indexed': 0, 'pages_indexed': 0,
        'cancelled': False, 'warnings': warnings, 'errors': [],
    }
    run = archive.begin_import_run('document', ', '.join(str(p) for p in paths)[:200])
    status = 'ok'
    total = len(files)
    try:
        for done, (path, label) in enumerate(files, 1):
            if cancel_event is not None and cancel_event.is_set():
                counts['cancelled'] = True
                status = 'cancelled'
                break
            extension = path.suffix.lower()
            if extension not in SUPPORTED:
                counts['files_unsupported'] += 1
                counts['warnings'].append(f'{path}: unsupported document type')
                if progress is not None:
                    progress(done, total, str(path), 'unsupported')
                continue
            try:
                size = path.stat().st_size
                if size > MAX_FILE_BYTES:
                    raise DocumentError(
                        f'file is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit')
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if catalog.has_file(digest):
                    counts['files_skipped'] += 1
                    if progress is not None:
                        progress(done, total, str(path), 'skipped')
                    continue
                extracted = extract_document(path)
                occurred, precision = _iso_from_mtime(path)
                metadata = _document_metadata(path, label, extension, size, digest,
                                              extracted, occurred, precision)
                attachments = extracted['pages'][:MAX_PAGES]
                with catalog.db:
                    catalog.add_file(digest, 'document', label, str(path), size, _utcnow())
                    revision_key = f'document|{label}'
                    revision_index = catalog.db.execute(
                        'SELECT count(*) FROM records WHERE revision_key=?',
                        (revision_key,)).fetchone()[0] + 1
                    inserted = catalog.add_record(
                        digest, 'document', label, 'document', None,
                        occurred, precision, extracted['text'],
                        json.dumps(metadata, ensure_ascii=False), digest, _utcnow(),
                        revision_key=revision_key, revision_index=revision_index,
                        attachments_json=json.dumps(attachments, ensure_ascii=False))
                if inserted:
                    counts['records_imported'] += 1
                    counts['characters_indexed'] += len(extracted['text'])
                    counts['pages_indexed'] += len(attachments)
                else:
                    counts['records_duplicate'] += 1
                counts['files_imported'] += 1
                if progress is not None:
                    progress(done, total, str(path), 'imported')
            except (DocumentError, OSError, ValueError) as exc:
                counts['extraction_failures'] += 1
                counts['errors'].append({'path': str(path),
                                         'error': type(exc).__name__ + ': ' + str(exc)})
                if progress is not None:
                    progress(done, total, str(path), 'error')
    except Exception as exc:
        status = 'error'
        counts['errors'].append({'path': '', 'error': type(exc).__name__ + ': ' + str(exc)})
        raise
    finally:
        catalog.close()
        archive.finish_import_run(
            run, status, len(files), counts['files_imported'],
            counts['records_imported'], counts['files_skipped'],
            counts['extraction_failures'])
        archive.db.close()
    counts['run_id'] = run
    return counts
