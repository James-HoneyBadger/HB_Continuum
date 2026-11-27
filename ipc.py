# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Versioned, newline-delimited JSON IPC for the desktop shell.

One JSON object per line. Requests carry a protocol_version, request_id,
method, and params. Responses carry the same protocol_version and
request_id with either result or error. Long-running jobs emit progress
events and a terminal job_complete or job_error event.
"""
import json, sqlite3, sys, threading, uuid
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
