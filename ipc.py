# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Versioned, newline-delimited JSON IPC for the desktop shell.

One JSON object per line. Requests carry a protocol_version, request_id,
method, and params. Responses carry the same protocol_version and
request_id with either result or error. Long-running jobs emit progress
events and a terminal job_complete or job_error event.
"""
import hashlib, json, sqlite3, sys, threading, uuid
from pathlib import Path

PROTOCOL_VERSION = 1
SEARCH_CAP = 5000

def _error(request_id, code, message):
    return {'protocol_version': PROTOCOL_VERSION, 'request_id': request_id,
            'error': {'code': code, 'message': message}}

def _result(request_id, result):
    return {'protocol_version': PROTOCOL_VERSION, 'request_id': request_id, 'result': result}

def _event(kind, **payload):
    return {'protocol_version': PROTOCOL_VERSION, 'event': kind, **payload}

def _archive_stats(root):
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        raise IPCError('ARCHIVE_NOT_AVAILABLE', 'The selected archive has no archive.sqlite3')
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    try:
        messages = conn.execute('SELECT count(*) FROM messages').fetchone()[0]
        origins = conn.execute('SELECT count(*) FROM origins').fetchone()[0]
    finally:
        conn.close()
    return {'messages': messages, 'origins': origins}

def _valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

def _ro_connect(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    return conn

def _message(root, digest):
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        raise IPCError('ARCHIVE_NOT_AVAILABLE', 'The selected archive has no archive.sqlite3')
    conn = _ro_connect(path)
    try:
        row = conn.execute(
            'SELECT subject,sender,date,message_id,reply_to,body FROM messages WHERE hash=?',
            (digest,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise IPCError('NOT_FOUND', 'message not found')
    return {'hash': digest, 'subject': row[0] or '', 'sender': row[1] or '',
            'date': row[2] or '', 'message_id': row[3] or '', 'reply_to': row[4] or '',
            'body': row[5] or ''}

def _thread_hashes(conn, digest):
    row = conn.execute('SELECT message_id,reply_to FROM messages WHERE hash=?', (digest,)).fetchone()
    if row is None:
        raise IPCError('NOT_FOUND', 'message not found')
    visited = {digest}
    frontier = {value for value in row if value}
    identifiers = set()
    while frontier:
        value = frontier.pop()
        if value in identifiers:
            continue
        identifiers.add(value)
        for member, mid, parent in conn.execute(
                'SELECT hash,message_id,reply_to FROM messages WHERE message_id=? OR reply_to=?',
                (value, value)):
            visited.add(member)
            frontier.update(v for v in (mid, parent) if v and v not in identifiers)
    return sorted(visited)

def _thread(root, digest):
    path = Path(root) / 'archive.sqlite3'
    if not path.is_file():
        raise IPCError('ARCHIVE_NOT_AVAILABLE', 'The selected archive has no archive.sqlite3')
    conn = _ro_connect(path)
    try:
        members = _thread_hashes(conn, digest)
        messages = []
        for member in members:
            row = conn.execute(
                'SELECT subject,sender,date,body FROM messages WHERE hash=?', (member,)).fetchone()
            messages.append({'hash': member, 'subject': row[0] or '', 'sender': row[1] or '',
                             'date': row[2] or '', 'body': row[3] or ''})
    finally:
        conn.close()
    return {'hash': digest, 'messages': messages}

def _record(root, record_id):
    path = Path(root) / 'catalog.sqlite3'
    if not path.is_file():
        raise IPCError('CATALOG_NOT_AVAILABLE', 'The selected archive has no catalog.sqlite3')
    conn = _ro_connect(path)
    try:
        row = conn.execute(
            'SELECT record_id,source_type,source_key,record_kind,actor,occurred_at,body,original_json '
            'FROM records WHERE record_id=?', (record_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise IPCError('NOT_FOUND', 'record not found')
    return {'record_id': row[0], 'source_type': row[1], 'source_key': row[2],
            'record_kind': row[3], 'actor': row[4] or '', 'occurred_at': row[5] or '',
            'body': row[6] or '', 'original_json': row[7] or ''}

def _verify(root):
    root = Path(root)
    path = root / 'archive.sqlite3'
    if not path.is_file():
        raise IPCError('ARCHIVE_NOT_AVAILABLE', 'The selected archive has no archive.sqlite3')
    conn = _ro_connect(path)
    try:
        hashes = [h for h, in conn.execute('SELECT hash FROM messages')]
    finally:
        conn.close()
    bad = []
    for h in hashes:
        if not _valid_hash(h):
            bad.append(h)
            continue
        raw = root / 'raw' / (h + '.eml')
        try:
            if raw.is_symlink() or not raw.is_file():
                bad.append(h)
                continue
            with raw.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != h:
                    bad.append(h)
        except OSError:
            bad.append(h)
    return {'checked': len(hashes), 'bad': bad}

def _import_eml(root, paths):
    from dispatch import Archive
    if not isinstance(paths, list):
        raise IPCError('INVALID_PARAMS', 'paths must be a list')
    files = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            files.extend(sorted(q for q in path.glob('*.eml') if q.is_file() and not q.name.startswith('.')))
        elif path.is_file():
            files.append(path)
    archive = Archive(root)
    imported = []
    errors = []
    try:
        before = {h for h, in archive.db.execute('SELECT hash FROM messages')}
        for f in files:
            try:
                digest = archive.ingest(f.read_bytes())
                if digest not in before:
                    imported.append(digest)
            except Exception as exc:
                errors.append({'path': str(f), 'error': type(exc).__name__ + ': ' + str(exc)})
    finally:
        archive.db.close()
    return {'files_seen': len(files), 'imported': len(imported), 'hashes': imported, 'errors': errors}

def _preferences(root):
    from preferences import FIELDS, load as load_prefs
    values = load_prefs(root)
    fields = []
    for key, (group, label, default, allowed) in FIELDS.items():
        if isinstance(default, bool):
            kind = 'bool'
        elif isinstance(default, int):
            kind = 'int'
        elif allowed:
            kind = 'choice'
        else:
            kind = 'text'
        fields.append({'key': key, 'group': group, 'label': label, 'kind': kind,
                       'default': default, 'allowed': list(allowed) if allowed else None})
    return {'values': values, 'fields': fields}

def _preferences_set(root, values):
    from preferences import save as save_prefs, validate
    if not isinstance(values, dict):
        raise IPCError('INVALID_PARAMS', 'values must be an object')
    validated = validate(values)
    save_prefs(root, validated)
    return {'values': validated}

RESEARCH_TABLES = ('workspaces', 'searches', 'tags', 'fields', 'reports')

def _research_list(root, table):
    if table not in RESEARCH_TABLES:
        raise IPCError('INVALID_PARAMS', 'table must be one of ' + ', '.join(RESEARCH_TABLES))
    path = Path(root) / 'research.sqlite3'
    if not path.is_file():
        return {'table': table, 'rows': []}
    conn = _ro_connect(path)
    try:
        rows = conn.execute('SELECT * FROM ' + table).fetchall()
    finally:
        conn.close()
    return {'table': table, 'rows': [list(r) for r in rows]}

def _research_results(root, workspace, name):
    research_path = Path(root) / 'research.sqlite3'
    archive_path = Path(root) / 'archive.sqlite3'
    if not research_path.is_file():
        raise IPCError('NOT_FOUND', 'no research overlay')
    conn = _ro_connect(research_path)
    try:
        row = conn.execute('SELECT query,tag,limit_n FROM searches WHERE workspace=? AND name=?',
                           (workspace, name)).fetchone()
        if row is None:
            raise IPCError('NOT_FOUND', 'unknown saved search')
        query, tag, limit_n = row
        tagged = None if not tag else {h for h, in conn.execute(
            'SELECT DISTINCT hash FROM tags WHERE tag=?', (tag,))}
    finally:
        conn.close()
    if not archive_path.is_file():
        raise IPCError('ARCHIVE_NOT_AVAILABLE', 'The selected archive has no archive.sqlite3')
    aconn = _ro_connect(archive_path)
    try:
        if query:
            sql = ('SELECT m.hash,m.subject,m.sender,m.date,m.message_id,m.reply_to '
                   'FROM search JOIN messages m ON m.hash=search.hash '
                   'WHERE search MATCH ? ORDER BY m.rowid DESC')
            params = (query,)
        else:
            sql = 'SELECT hash,subject,sender,date,message_id,reply_to FROM messages ORDER BY rowid DESC'
            params = ()
        rows = []
        try:
            cursor = aconn.execute(sql, params)
        except sqlite3.OperationalError:
            cursor = iter(())
        for r in cursor:
            if tagged is None or r[0] in tagged:
                rows.append(dict(zip(('hash', 'subject', 'sender', 'date', 'message_id', 'reply_to'), r)))
                if len(rows) >= limit_n:
                    break
    finally:
        aconn.close()
    return {'workspace': workspace, 'name': name, 'count': len(rows), 'results': rows}

class IPCError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

class IPCServer:
    def __init__(self, root, out=None, err=None):
        self.root = Path(root).expanduser()
        self.out = out if out is not None else sys.stdout
        self.err = err if err is not None else sys.stderr
        self._jobs = {}
        self._lock = threading.Lock()

    def _write(self, obj):
        line = json.dumps(obj, ensure_ascii=False)
        with self._lock:
            self.out.write(line + '\n')
            self.out.flush()

    def _catalog_stats(self):
        from catalog import Catalog
        catalog = Catalog(self.root)
        try:
            return catalog.stats()
        finally:
            catalog.close()

    def _search(self, params):
        from unified import search_unified
        query = params.get('query')
        if not isinstance(query, str) or not query.strip():
            raise IPCError('INVALID_PARAMS', 'search requires a non-empty query string')
        sources = params.get('sources', ('email', 'facebook'))
        if isinstance(sources, str):
            sources = tuple(x.strip() for x in sources.split(',') if x.strip())
        sources = tuple(sources) or ('email', 'facebook')
        if not all(s in ('email', 'facebook') for s in sources):
            raise IPCError('INVALID_PARAMS', 'sources must be email and/or facebook')
        page = max(1, int(params.get('page', 1)))
        page_size = max(1, min(int(params.get('page_size', 20)), 1000))
        results = search_unified(self.root, query, limit=SEARCH_CAP, sources=sources)
        start = (page - 1) * page_size
        return {'items': results[start:start + page_size], 'page': page,
                'page_size': page_size, 'has_more': len(results) > start + page_size,
                'total': len(results)}

    def _start_summarize(self, params):
        from preferences import load as load_prefs
        from summarize import Summarizer, OllamaError
        prefs = load_prefs(self.root)
        if not (prefs.get('ai_enabled') and prefs.get('ai_backend') == 'ollama'):
            raise IPCError('AI_DISABLED', 'AI is disabled; enable it before summarizing')
        hashes = params.get('hashes')
        if hashes is not None and (not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes)):
            raise IPCError('INVALID_PARAMS', 'hashes must be a list of strings')
        summary_type = params.get('summary_type', 'message')
        if summary_type not in ('message', 'thread'):
            raise IPCError('INVALID_PARAMS', 'summary_type must be message or thread')
        job_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        job = {'id': job_id, 'cancel_event': cancel_event}
        self._jobs[job_id] = job

        def worker():
            summarizer = Summarizer(self.root)
            try:
                if not summarizer.enabled():
                    raise IPCError('AI_DISABLED', 'AI is disabled; enable it before summarizing')

                def progress(done, total, digest, status):
                    self._write(_event('progress', job_id=job_id, done=done, total=total,
                                       hash=digest, status=status))

                if hashes is not None:
                    result = summarizer.summarize_batch(
                        hashes, summary_type, model=params.get('model'),
                        prompt_version=params.get('prompt_version'),
                        progress=progress, cancel_event=cancel_event)
                else:
                    result = summarizer.summarize_all(
                        summary_type, model=params.get('model'),
                        prompt_version=params.get('prompt_version'),
                        progress=progress, cancel_event=cancel_event)
                self._write(_event('job_complete', job_id=job_id, result=result))
            except IPCError as exc:
                self._write(_event('job_error', job_id=job_id, code=exc.code, message=str(exc)))
            except OllamaError as exc:
                self._write(_event('job_error', job_id=job_id, code='OLLAMA_ERROR', message=str(exc)))
            except Exception as exc:
                self._write(_event('job_error', job_id=job_id, code='INTERNAL_ERROR',
                                   message=type(exc).__name__ + ': ' + str(exc)))
            finally:
                summarizer.close()
                job['done'] = True

        threading.Thread(target=worker, daemon=True).start()
        return {'job_id': job_id, 'status': 'started'}

    def _cancel(self, params):
        job_id = params.get('job_id')
        job = self._jobs.get(job_id) if isinstance(job_id, str) else None
        if job is None:
            raise IPCError('UNKNOWN_JOB', 'no such job')
        job['cancel_event'].set()
        return {'job_id': job_id, 'status': 'cancelling'}

    def handle(self, request):
        """Validate and dispatch one request. Returns a response dict or None for shutdown."""
        if not isinstance(request, dict):
            return _error(None, 'INVALID_REQUEST', 'request must be an object')
        if request.get('protocol_version') != PROTOCOL_VERSION:
            return _error(request.get('request_id'), 'UNSUPPORTED_VERSION',
                          f'supported protocol_version is {PROTOCOL_VERSION}')
        request_id = request.get('request_id')
        method = request.get('method')
        params = request.get('params', {}) if isinstance(request.get('params'), dict) else {}
        try:
            if method == 'ping':
                return _result(request_id, {'pong': True, 'protocol_version': PROTOCOL_VERSION})
            if method == 'stats':
                return _result(request_id, {'archive': _archive_stats(self.root),
                                            'catalog': self._catalog_stats()})
            if method == 'search':
                return _result(request_id, self._search(params))
            if method == 'message':
                return _result(request_id, _message(self.root, params.get('hash')))
            if method == 'thread':
                return _result(request_id, _thread(self.root, params.get('hash')))
            if method == 'record':
                return _result(request_id, _record(self.root, params.get('record_id')))
            if method == 'verify':
                return _result(request_id, _verify(self.root))
            if method == 'import_eml':
                return _result(request_id, _import_eml(self.root, params.get('paths', [])))
            if method == 'preferences':
                return _result(request_id, _preferences(self.root))
            if method == 'preferences_set':
                return _result(request_id, _preferences_set(self.root, params.get('values')))
            if method == 'research_list':
                return _result(request_id, _research_list(self.root, params.get('table')))
            if method == 'research_results':
                return _result(request_id, _research_results(self.root, params.get('workspace'), params.get('name')))
            if method == 'summarize':
                return _result(request_id, self._start_summarize(params))
            if method == 'cancel':
                return _result(request_id, self._cancel(params))
            if method == 'shutdown':
                self._shutdown()
                return None
            return _error(request_id, 'UNKNOWN_METHOD', f'unknown method {method!r}')
        except IPCError as exc:
            return _error(request_id, exc.code, str(exc))
        except (ValueError, sqlite3.Error) as exc:
            return _error(request_id, 'INVALID_PARAMS', str(exc))
        except Exception as exc:
            return _error(request_id, 'INTERNAL_ERROR', type(exc).__name__ + ': ' + str(exc))

    def _shutdown(self):
        for job in self._jobs.values():
            job['cancel_event'].set()

    def serve(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._write(_error(None, 'INVALID_JSON', 'request is not valid JSON'))
                continue
            response = self.handle(request)
            if response is not None:
                self._write(response)
            if request.get('method') == 'shutdown':
                break
