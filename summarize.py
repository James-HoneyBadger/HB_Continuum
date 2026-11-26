# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local, opt-in message and thread summarization via a loopback Ollama.

Summaries are derived, replaceable information. They are never written to
archive.sqlite3 and never modify raw EML. Every request passes the opt-in
gate first: ai.enabled must be true and ai.backend must be 'ollama'.
"""
import hashlib, json, sqlite3, threading, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from preferences import load as load_prefs
from research import SUMMARIES_DDL

MAX_RESPONSE = 1_000_000

SYSTEM_PROMPT = (
    'You summarize archived correspondence for its owner. Use only the text '
    'supplied to you. Never invent facts, dates, amounts, names, or motives. '
    'If something is not in the supplied text, say it is not present.'
)

class OllamaError(RuntimeError):
    pass

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OllamaError(f'refusing HTTP redirect to {newurl}')

def _utcnow():
    return datetime.now(timezone.utc).isoformat()

def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _ro_connect(root):
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    return conn

def _message_prompt_v1(meta, max_chars):
    body = meta['body'][:max_chars]
    return (f'Summarize this email in three concise sentences.\n'
            f'Subject: {meta["subject"]}\nFrom: {meta["sender"]}\nDate: {meta["date"]}\n\n{body}')

def _thread_prompt_v1(entries, max_chars):
    lines = []
    budget = max_chars
    for i, entry in enumerate(entries):
        chunk = f'[{i+1}] {entry["subject"]} | {entry["sender"]} | {entry["date"]}\n{entry["body"]}'
        if budget <= 0:
            break
        chunk = chunk[:budget]
        lines.append(chunk)
        budget -= len(chunk) + 1
    return ('Summarize this conversation as a thread: who participated, what was '
            'discussed, what was decided or committed, and any open questions.\n\n'
            + '\n\n'.join(lines))

PROMPTS = {
    '1': (_message_prompt_v1, _thread_prompt_v1),
}

def _date_key(date_text):
    try:
        parsed = parsedate_to_datetime(date_text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (0, parsed.timestamp())
    except (ValueError, TypeError, OverflowError, OSError):
        return (1, 0.0)

class Summarizer:
    def __init__(self, root, prefs=None):
        self.root = Path(root).expanduser()
        self.prefs = prefs if prefs is not None else load_prefs(self.root)
        self.db = sqlite3.connect(self.root / 'research.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SUMMARIES_DDL)
        self._opener = urllib.request.build_opener(_NoRedirect(), urllib.request.ProxyHandler({}))
        self._cancelled = threading.Event()

    def close(self):
        self.db.close()

    def cancel(self):
        self._cancelled.set()

    def enabled(self):
        return bool(self.prefs.get('ai_enabled')) and self.prefs.get('ai_backend') == 'ollama'

    def _guard(self):
        if not self.enabled():
            raise ValueError('AI is disabled; set ai.enabled and ai.backend=ollama in preferences')

    def _validate_endpoint(self):
        parts = urllib.parse.urlsplit(self.prefs['ai_endpoint'])
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            raise ValueError('ai.endpoint must be an http(s) URL')
        if parts.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('ai.endpoint must be a loopback address')

    def _chat(self, system, user, model):
        self._guard()
        self._validate_endpoint()
        payload = {'model': model, 'stream': False,
                   'messages': [{'role': 'system', 'content': system},
                                {'role': 'user', 'content': user}]}
        request = urllib.request.Request(
            self.prefs['ai_endpoint'].rstrip('/') + '/api/chat',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with self._opener.open(request, timeout=self.prefs['ai_timeout']) as response:
                data = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            raise OllamaError(f'Ollama HTTP {exc.code}: {exc.reason}') from None
        except urllib.error.URLError as exc:
            raise OllamaError(f'cannot reach Ollama at {self.prefs["ai_endpoint"]}: {exc.reason}') from None
        except (TimeoutError, OSError) as exc:
            raise OllamaError(f'Ollama request failed: {exc}') from None
        if len(data) > MAX_RESPONSE:
            raise OllamaError('Ollama response exceeds size limit')
        try:
            return json.loads(data.decode('utf-8'))['message']['content']
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise OllamaError(f'unexpected Ollama response: {exc}') from None

    def _model(self, model):
        return model or self.prefs['ai_model']

    def _prompt_version(self, prompt_version):
        return prompt_version or self.prefs['ai_prompt_version']

    def _is_current(self, digest, summary_type, model, prompt_version, input_digest):
        row = self.db.execute(
            'SELECT input_digest FROM summaries WHERE message_hash=? AND summary_type=? AND model_name=? AND prompt_version=?',
            (digest, summary_type, model, prompt_version)).fetchone()
        return row is not None and row[0] == input_digest

    def _store(self, digest, summary_type, model, prompt_version, summary, input_digest, thread_members):
        existed = self.db.execute(
            'SELECT 1 FROM summaries WHERE message_hash=? AND summary_type=? AND model_name=? AND prompt_version=?',
            (digest, summary_type, model, prompt_version)).fetchone() is not None
        self.db.execute(
            'INSERT OR REPLACE INTO summaries VALUES(?,?,?,?,?,?,?,?)',
            (digest, summary_type, model, prompt_version, summary, _utcnow(), input_digest, thread_members))
        self.db.commit()
        return 'regenerated' if existed else 'summarized'

    def summarize_message(self, digest, model=None, prompt_version=None, force=False):
        self._guard()
        model = self._model(model)
        prompt_version = self._prompt_version(prompt_version)
        message_fn, _ = PROMPTS.get(prompt_version, (None, None))
        if message_fn is None:
            raise ValueError(f'Unknown prompt version {prompt_version!r}')
        conn = _ro_connect(self.root)
        try:
            row = conn.execute('SELECT subject,sender,date,body FROM messages WHERE hash=?', (digest,)).fetchone()
            if row is None:
                raise ValueError('Unknown message')
            meta = {'subject': row[0] or '', 'sender': row[1] or '', 'date': row[2] or '', 'body': row[3] or ''}
        finally:
            conn.close()
        user = message_fn(meta, self.prefs['ai_max_input_chars'])
        input_digest = _digest(user)
        if not force and self._is_current(digest, 'message', model, prompt_version, input_digest):
            return 'skipped'
        summary = self._chat(SYSTEM_PROMPT, user, model)
        return self._store(digest, 'message', model, prompt_version, summary, input_digest, None)

    def summarize_thread(self, digest, model=None, prompt_version=None, force=False):
        self._guard()
        model = self._model(model)
        prompt_version = self._prompt_version(prompt_version)
        _, thread_fn = PROMPTS.get(prompt_version, (None, None))
        if thread_fn is None:
            raise ValueError(f'Unknown prompt version {prompt_version!r}')
        conn = _ro_connect(self.root)
        try:
            members = _thread_hashes(conn, digest)
            entries = []
            for member in members:
                row = conn.execute('SELECT subject,sender,date,body FROM messages WHERE hash=?', (member,)).fetchone()
                entries.append({'hash': member, 'subject': row[0] or '', 'sender': row[1] or '',
                                'date': row[2] or '', 'body': row[3] or ''})
            key = _canonical_key(conn, members)
        finally:
            conn.close()
        entries.sort(key=lambda e: (_date_key(e['date']), e['hash']))
        user = thread_fn(entries, self.prefs['ai_max_input_chars'])
        input_digest = _digest(user)
        if not force and self._is_current(key, 'thread', model, prompt_version, input_digest):
            return 'skipped'
        summary = self._chat(SYSTEM_PROMPT, user, model)
        return self._store(key, 'thread', model, prompt_version, summary, input_digest, json.dumps(members))

    def summarize_batch(self, hashes, summary_type='message', model=None, prompt_version=None,
                        force=False, progress=None, cancel_event=None):
        hashes = list(dict.fromkeys(hashes))
        counts = {'total': len(hashes), 'summarized': 0, 'regenerated': 0, 'skipped': 0, 'cancelled': 0}
        for i, digest in enumerate(hashes):
            if self._cancelled.is_set() or (cancel_event is not None and cancel_event.is_set()):
                counts['cancelled'] = len(hashes) - i
                if progress:
                    progress(i, len(hashes), digest, 'cancelled')
                break
            try:
                result = self.summarize_message(digest, model, prompt_version, force) if summary_type == 'message' \
                    else self.summarize_thread(digest, model, prompt_version, force)
            except OllamaError:
                raise
            if result in ('summarized', 'regenerated'):
                counts[result] += 1
                status = result
            else:
                counts['skipped'] += 1
                status = 'skipped'
            if progress:
                progress(i + 1, len(hashes), digest, status)
        return counts

    def summarize_all(self, summary_type='message', model=None, prompt_version=None,
                      force=False, progress=None, cancel_event=None):
        conn = _ro_connect(self.root)
        try:
            hashes = [h for h, in conn.execute('SELECT hash FROM messages ORDER BY rowid DESC')]
        finally:
            conn.close()
        return self.summarize_batch(hashes, summary_type, model, prompt_version, force, progress, cancel_event)

    def list_summaries(self, digest):
        rows = self.db.execute(
            'SELECT summary_type, model_name, prompt_version, summary_text, created_at, input_digest '
            'FROM summaries WHERE message_hash=? ORDER BY created_at DESC', (digest,)).fetchall()
        return [dict(zip(('summary_type', 'model_name', 'prompt_version', 'summary_text',
                          'created_at', 'input_digest'), row)) for row in rows]

    def delete(self, digest, summary_type=None, model=None, prompt_version=None):
        sql = 'DELETE FROM summaries WHERE message_hash=?'
        params = [digest]
        if summary_type:
            sql += ' AND summary_type=?'
            params.append(summary_type)
        if model:
            sql += ' AND model_name=?'
            params.append(model)
        if prompt_version:
            sql += ' AND prompt_version=?'
            params.append(prompt_version)
        with self.db:
            cur = self.db.execute(sql, params)
        return {'deleted': cur.rowcount}


def _thread_hashes(conn, digest):
    row = conn.execute('SELECT message_id,reply_to FROM messages WHERE hash=?', (digest,)).fetchone()
    if row is None:
        raise ValueError('Unknown message')
    visited = {digest}
    frontier = {value for value in row if value}
    identifiers = set()
    while frontier:
        value = frontier.pop()
        if value in identifiers:
            continue
        identifiers.add(value)
        for member, mid, parent in conn.execute(
                'SELECT hash,message_id,reply_to FROM messages WHERE message_id=? OR reply_to=?', (value, value)):
            visited.add(member)
            frontier.update(v for v in (mid, parent) if v and v not in identifiers)
    return sorted(visited)

def _canonical_key(conn, hashes):
    rows = {}
    for h in hashes:
        row = conn.execute('SELECT message_id,reply_to FROM messages WHERE hash=?', (h,)).fetchone()
        rows[h] = row or (None, None)
    identifiers = {mid for mid, _ in rows.values() if mid}
    roots = [h for h, (mid, reply) in rows.items() if not reply or reply not in identifiers]
    return min(roots or hashes)
