# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local read-only email archive. No network access except explicit sync."""
import shutil, argparse, hashlib, imaplib, sqlite3, ssl, json, os, tempfile, time
from pathlib import Path
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

__version__ = '0.3.0'

SYNC_MAX_ATTEMPTS = 3

_HTML_BLOCK_TAGS = frozenset({'br','p','div','tr','li','hr','h1','h2','h3','h4','h5','h6','blockquote','pre'})
_HTML_SKIP_TAGS = frozenset({'script','style','head','title'})

class _HTMLText(HTMLParser):
    """Collect visible text from HTML markup, dropping scripts, styles and tags."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0; self._chunks = []
    def handle_starttag(self, tag, attrs):
        if tag in _HTML_SKIP_TAGS: self._skip += 1
        elif tag in _HTML_BLOCK_TAGS: self._chunks.append('\n')
    def handle_startendtag(self, tag, attrs):
        if tag in _HTML_BLOCK_TAGS: self._chunks.append('\n')
    def handle_endtag(self, tag):
        if tag in _HTML_SKIP_TAGS: self._skip = max(0, self._skip - 1)
        elif tag in _HTML_BLOCK_TAGS: self._chunks.append('\n')
    def handle_data(self, data):
        if not self._skip: self._chunks.append(data)
    def text(self):
        return ''.join(self._chunks)

def html_to_text(markup):
    """Best-effort plain text from HTML; falls back to the raw markup if unparseable."""
    if not markup: return ''
    parser = _HTMLText()
    try:
        parser.feed(markup); parser.close()
    except Exception:
        return markup
    lines = (' '.join(line.split()) for line in parser.text().splitlines())
    return '\n'.join(line for line in lines if line)

class Archive:
    def __init__(self, root):
        self.root = Path(root).expanduser(); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.raw = self.root / 'raw'; self.raw.mkdir(mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'archive.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS messages(hash TEXT PRIMARY KEY, subject TEXT, sender TEXT, date TEXT, message_id TEXT, reply_to TEXT, body TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(hash UNINDEXED, subject, sender, body);
        CREATE INDEX IF NOT EXISTS messages_message_id ON messages(message_id);
        CREATE INDEX IF NOT EXISTS messages_reply_to ON messages(reply_to);
        CREATE TABLE IF NOT EXISTS origins(account TEXT, folder TEXT, validity TEXT, uid TEXT, hash TEXT NOT NULL REFERENCES messages(hash), PRIMARY KEY(account,folder,validity,uid));
        CREATE TABLE IF NOT EXISTS sync_failures(account TEXT NOT NULL, folder TEXT NOT NULL, validity TEXT NOT NULL, uid TEXT NOT NULL, error TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1, last_seen TEXT NOT NULL, PRIMARY KEY(account,folder,validity,uid));
        CREATE TABLE IF NOT EXISTS attachments(message TEXT NOT NULL REFERENCES messages(hash), filename TEXT NOT NULL, content_type TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(message,filename,sha256));
        CREATE INDEX IF NOT EXISTS attachments_sha256 ON attachments(sha256);''')
    @staticmethod
    def _part_text(part):
        """Extract decoded text from a MIME part; never raises on hostile charsets."""
        payload = part.get_payload(decode=True)
        if payload is None:
            raw = part.get_payload()
            return raw if isinstance(raw, str) else ''
        if not isinstance(payload, bytes):
            return str(payload)
        charset = part.get_content_charset() or 'utf-8'
        try:
            return payload.decode(charset, errors='replace')
        except LookupError:
            return payload.decode('utf-8', errors='replace')
    @staticmethod
    def _is_body_part(part):
        """True for leaf text parts, attached or not, that can carry readable text."""
        return not part.is_multipart() and part.get_content_type() in ('text/plain','text/html')
    def _body_of(self, msg):
        """Searchable body: prefer ordinary text/plain, then HTML, then attached text.

        Attached text only contributes when the message has no ordinary body, so
        forwarded files never pollute subject-level search results.
        """
        plain, html, filed = [], [], []
        for part in msg.walk():
            if not self._is_body_part(part): continue
            text=self._part_text(part)
            if not text.strip(): continue
            if part.get_filename() is not None or part.get_content_disposition()=='attachment':
                filed.append(text)
            elif part.get_content_type()=='text/plain': plain.append(text)
            else: html.append(text)
        return '\n'.join(plain) or html_to_text('\n'.join(html)) or '\n'.join(filed)
    @staticmethod
    def _attachment_parts(msg):
        """Yield (filename, content_type, payload) for parts the sender marked as files."""
        for part in msg.walk():
            if part.is_multipart(): continue
            filename=part.get_filename()
            if filename is None and part.get_content_disposition()!='attachment': continue
            payload=part.get_payload(decode=True)
            if not isinstance(payload,bytes): continue
            yield (str(filename or 'attachment'), part.get_content_type(), payload)
    def _store_attachment(self, payload):
        """Store bytes content-addressed and return their SHA-256.

        Identical attachments across messages and accounts occupy one file, and an
        existing blob is never overwritten; a corrupted blob is reported instead.
        """
        digest=hashlib.sha256(payload).hexdigest()
        target=self.root/'attachments'/digest[:2]/digest
        if target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError('Attachment integrity mismatch')
            return digest
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as f:
            f.write(payload); f.flush(); os.fsync(f.fileno()); tmp=f.name
        os.replace(tmp,target)
        return digest
    def ingest(self, raw, origin=None):
        if len(raw) > 64 * 1024 * 1024: raise ValueError('Message exceeds 64 MiB limit')
        digest = hashlib.sha256(raw).hexdigest(); target = self.raw / (digest+'.eml')
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=self.raw, delete=False) as f:
                f.write(raw); f.flush(); os.fsync(f.fileno()); tmp=f.name
            os.replace(tmp,target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError('Raw integrity mismatch')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        body=self._body_of(msg)
        attachments=[(name,ctype,len(payload),self._store_attachment(payload))
                     for name,ctype,payload in self._attachment_parts(msg)]
        fields=[str(msg.get(k,'')) for k in ('Subject','From','Date','Message-ID','In-Reply-To')]
        with self.db:
            cur=self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?)',(digest,*fields,body))
            if cur.rowcount: self.db.execute('INSERT INTO search VALUES(?,?,?,?)',(digest,fields[0],fields[1],body))
            for filename,content_type,size,sha256 in attachments:
                self.db.execute('INSERT OR IGNORE INTO attachments VALUES(?,?,?,?,?)',(digest,filename,content_type,size,sha256))
            if origin:
                self.db.execute('INSERT OR IGNORE INTO origins VALUES(?,?,?,?,?)',(*origin,digest))
                if self.db.execute('SELECT hash FROM origins WHERE account=? AND folder=? AND validity=? AND uid=?',origin).fetchone()[0]!=digest: raise ValueError('Origin conflict')
        return digest
    def find(self, query, limit=100):
        limit=max(1,min(int(limit),5000))
        try:
            return self.db.execute('SELECT hash,subject,sender FROM search WHERE search MATCH ? LIMIT ?', (query,limit)).fetchall()
        except sqlite3.OperationalError:
            phrase='"'+query.replace('"','""')+'"'
            try:
                return self.db.execute('SELECT hash,subject,sender FROM search WHERE search MATCH ? LIMIT ?', (phrase,limit)).fetchall()
            except sqlite3.OperationalError:
                return []
    def reindex(self):
        """Rebuild message metadata and the search index from the stored raw files.

        Safe and idempotent: raw mail is only read, never rewritten, and an
        interrupted run can simply be restarted. Repairs archives written by older
        versions (for example HTML-only mail that previously stored an empty body).
        """
        rebuilt=0
        for (digest,) in self.db.execute('SELECT hash FROM messages').fetchall():
            path=self.raw/(digest+'.eml')
            if not path.is_file(): continue
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('Integrity mismatch')
            msg=BytesParser(policy=policy.default).parsebytes(raw)
            body=self._body_of(msg)
            attachments=[(name,ctype,len(payload),self._store_attachment(payload))
                         for name,ctype,payload in self._attachment_parts(msg)]
            fields=[str(msg.get(k,'')) for k in ('Subject','From','Date','Message-ID','In-Reply-To')]
            with self.db:
                self.db.execute('UPDATE messages SET subject=?,sender=?,date=?,message_id=?,reply_to=?,body=? WHERE hash=?',(*fields,body,digest))
                self.db.execute('DELETE FROM search WHERE hash=?',(digest,))
                self.db.execute('INSERT INTO search VALUES(?,?,?,?)',(digest,fields[0],fields[1],body))
                self.db.execute('DELETE FROM attachments WHERE message=?',(digest,))
                for filename,content_type,size,sha256 in attachments:
                    self.db.execute('INSERT OR IGNORE INTO attachments VALUES(?,?,?,?,?)',(digest,filename,content_type,size,sha256))
            rebuilt+=1
        return rebuilt
    def attachments(self, digest):
        """Attachment metadata for one message, ordered by filename."""
        return self.db.execute('SELECT filename,content_type,size,sha256 FROM attachments WHERE message=? ORDER BY filename',(digest,)).fetchall()
    def attachment_bytes(self, sha256):
        """Return stored attachment bytes after verifying the digest."""
        if not isinstance(sha256,str) or len(sha256)!=64 or any(c not in '0123456789abcdef' for c in sha256):
            raise ValueError('Invalid attachment hash')
        path=self.root/'attachments'/sha256[:2]/sha256
        if not path.is_file(): raise ValueError('Unknown attachment')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=sha256: raise ValueError('Attachment integrity mismatch')
        return data
    def verify(self):
        return [h for (h,) in self.db.execute('SELECT hash FROM messages') if not (p:=self.raw/(h+'.eml')).is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h]
    def verify_attachments(self):
        """Attachment blobs that are missing or no longer match their stored digest."""
        return [sha for (sha,) in self.db.execute('SELECT DISTINCT sha256 FROM attachments')
                if not (p:=self.root/'attachments'/sha[:2]/sha).is_file()
                or hashlib.sha256(p.read_bytes()).hexdigest()!=sha]
    def export(self, hashes, destination):
        dest=Path(destination)
        hashes=list(dict.fromkeys(hashes))
        if not hashes: raise ValueError('Select at least one message')
        for h in hashes:
            if not isinstance(h,str) or len(h)!=64 or any(x not in '0123456789abcdef' for x in h):
                raise ValueError('Invalid message hash')
            if not self.db.execute('SELECT 1 FROM messages WHERE hash=?',(h,)).fetchone():
                raise ValueError('Unknown message')
        dest.mkdir(mode=0o700,parents=True,exist_ok=False)
        try:
            manifest=[]
            for h in hashes:
                raw=(self.raw/(h+'.eml')).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=h: raise ValueError('Integrity mismatch')
                with os.fdopen(os.open(dest/(h+'.eml'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as output:
                    output.write(raw)
                origins=self.db.execute('SELECT account,folder,validity,uid FROM origins WHERE hash=? ORDER BY account,folder,validity,uid',(h,)).fetchall()
                manifest.append({'sha256':h,'file':h+'.eml','origins':origins})
            with os.fdopen(os.open(dest/'manifest.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as output:
                json.dump(manifest,output,indent=2)
        except Exception:
            shutil.rmtree(dest)
            raise
    def details(self, digest):
        row=self.db.execute('SELECT subject,sender,date,message_id,reply_to,body FROM messages WHERE hash=?',(digest,)).fetchone()
        if row is None: raise ValueError('Unknown message')
        return dict(zip(('subject','sender','date','message_id','reply_to','body'),row))
    def recent(self, limit=100):
        return self.db.execute('SELECT hash,subject,sender FROM messages ORDER BY rowid DESC LIMIT ?', (max(1,min(int(limit),5000)),)).fetchall()
    def timeline(self, sender=None, limit=100):
        """Chronological view of declared message dates; unparseable dates sort last."""
        from email.utils import parsedate_to_datetime
        from datetime import timezone
        sql='SELECT hash,subject,sender,date FROM messages'
        params=()
        if sender is not None:
            sql+=' WHERE sender=?'
            params=(sender,)
        def key(row):
            try:
                d=parsedate_to_datetime(row[3])
                if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
                return (0,d.timestamp(),row[0])
            except (ValueError,TypeError,OverflowError,OSError):
                return (1,0,row[0])
        return sorted(self.db.execute(sql,params),key=key)[:max(1,min(int(limit),5000))]
    def correspondents(self, limit=100):
        return self.db.execute(
            "SELECT sender, count(*) FROM messages GROUP BY sender ORDER BY count(*) DESC, sender LIMIT ?",
            (max(1,min(int(limit),5000)),)).fetchall()
    def thread(self, digest):
        """Return linked messages using Message-ID and In-Reply-To, not subject guesses."""
        row=self.db.execute('SELECT message_id,reply_to FROM messages WHERE hash=?',(digest,)).fetchone()
        if row is None: raise ValueError('Unknown message')
        visited={digest}
        frontier={value for value in row if value}
        identifiers=set()
        while frontier:
            value=frontier.pop()
            if value in identifiers: continue
            identifiers.add(value)
            for h,mid,parent in self.db.execute(
                'SELECT hash,message_id,reply_to FROM messages WHERE message_id=? OR reply_to=?',(value,value)):
                visited.add(h)
                frontier.update(v for v in (mid,parent) if v and v not in identifiers)
        return [self.details(h) | {'sha256':h} for h in sorted(visited)]
    def stats(self):
        return {'messages':self.db.execute('SELECT count(*) FROM messages').fetchone()[0],
                'origins':self.db.execute('SELECT count(*) FROM origins').fetchone()[0],
                'attachments':self.db.execute('SELECT count(*) FROM attachments').fetchone()[0]}
    def sync(self, host, user, password, folder='INBOX'):
        from sync_lock import sync_lock
        with sync_lock(self.root):
            return self._sync(host, user, password, folder)
    def _sync(self, host, user, password, folder):
        if folder.startswith('"') and folder.endswith('"'):
            folder=folder[1:-1]
        if not folder or any(c in folder for c in '\r\n\x00'):
            raise ValueError('Invalid mailbox name')
        quoted='"'+folder.replace('\\','\\\\').replace('"','\\"')+'"'
        if host.lower()=='imap.gmail.com':
            password=''.join(password.split())
        from preferences import load
        prefs=load(self.root)
        with imaplib.IMAP4_SSL(host, ssl_context=ssl.create_default_context(), timeout=prefs['network_timeout']) as m:
            m.login(user,password)
            if m.select(quoted,readonly=True)[0]!='OK': raise RuntimeError('Select failed')
            resp=m.response('UIDVALIDITY')[1]
            if not resp or resp[0] is None or not resp[0].decode().isdigit(): raise RuntimeError('Missing UIDVALIDITY')
            validity=resp[0].decode()
            status,data=m.uid('search',None,'ALL')
            if status!='OK': raise RuntimeError('Search failed')
            count=0
            for uid in data[0].split():
                origin=(host+'|'+user,folder,validity,uid.decode())
                if self.db.execute('SELECT 1 FROM origins WHERE account=? AND folder IN (?,?) AND validity=? AND uid=?',(origin[0],folder,quoted,validity,uid.decode())).fetchone(): continue
                attempts=self._failure_attempts(origin)
                if attempts>=SYNC_MAX_ATTEMPTS: continue
                try:
                    payload=[p[1] for p in self._fetch(m,uid) if isinstance(p,tuple)]
                    if len(payload)!=1: raise RuntimeError('Unexpected fetch response')
                    self.ingest(payload[0],origin); count+=1
                except Exception as error:
                    self._record_failure(origin,f'{type(error).__name__}: {error}')
                    raise
                if attempts:
                    with self.db: self.db.execute('DELETE FROM sync_failures WHERE account=? AND folder=? AND validity=? AND uid=?',origin)
                if prefs['batch_limit'] and count>=prefs['batch_limit']: break
            return count
    def _fetch(self, connection, uid, attempts=SYNC_MAX_ATTEMPTS):
        """Fetch one UID with BODY.PEEK, retrying transient connection aborts."""
        failure=None
        for attempt in range(attempts):
            try:
                status,parts=connection.uid('fetch',uid,'(BODY.PEEK[])')
                if status!='OK': raise RuntimeError('Fetch failed')
                return parts
            except imaplib.IMAP4.abort as error:
                failure=error
                if attempt+1<attempts: time.sleep(2**attempt)
        raise RuntimeError(f'Fetch failed after {attempts} attempts: {failure}')
    def _failure_attempts(self, origin):
        row=self.db.execute('SELECT attempts FROM sync_failures WHERE account=? AND folder=? AND validity=? AND uid=?',origin).fetchone()
        return row[0] if row else 0
    def _record_failure(self, origin, error):
        with self.db:
            self.db.execute('''INSERT INTO sync_failures(account,folder,validity,uid,error,attempts,last_seen)
                VALUES(?,?,?,?,?,1,datetime('now'))
                ON CONFLICT(account,folder,validity,uid) DO UPDATE SET attempts=attempts+1, error=excluded.error, last_seen=excluded.last_seen''',(*origin,error))
    def failures(self, limit=500):
        """Messages that could not be archived, with attempt counts, most recent first."""
        return self.db.execute('SELECT account,folder,validity,uid,attempts,error,last_seen FROM sync_failures ORDER BY last_seen DESC LIMIT ?',(max(1,min(int(limit),5000)),)).fetchall()

def main():
    import getpass
    p=argparse.ArgumentParser(); p.add_argument('--archive',default='~/.hb-dispatch'); p.add_argument('--version',action='version',version=f'%(prog)s {__version__}'); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('import'); q.add_argument('files',nargs='+'); q=sub.add_parser('search'); q.add_argument('query'); sub.add_parser('verify'); sub.add_parser('reindex'); q=sub.add_parser('failures'); q.add_argument('--limit',default=500); q=sub.add_parser('attachments'); q.add_argument('hash'); q=sub.add_parser('attachment'); q.add_argument('sha256'); q.add_argument('destination'); sub.add_parser('verify-attachments'); q=sub.add_parser('export'); q.add_argument('destination'); q.add_argument('hashes',nargs='+'); q=sub.add_parser('sync'); q.add_argument('host'); q.add_argument('user'); q.add_argument('--folder',default='INBOX'); sub.add_parser('gui')
    a=p.parse_args(); ar=Archive(a.archive)
    if a.cmd=='import':
        for f in a.files: print(ar.ingest(Path(f).read_bytes()))
    elif a.cmd=='search': print(json.dumps(ar.find(a.query),indent=2))
    elif a.cmd=='verify':
        bad=ar.verify(); print(json.dumps(bad)); return int(bool(bad))
    elif a.cmd=='reindex': print(ar.reindex())
    elif a.cmd=='attachments': print(json.dumps(ar.attachments(a.hash),indent=2))
    elif a.cmd=='attachment':
        data=ar.attachment_bytes(a.sha256)
        with os.fdopen(os.open(Path(a.destination),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as output:
            output.write(data)
    elif a.cmd=='verify-attachments':
        bad=ar.verify_attachments(); print(json.dumps(bad)); return int(bool(bad))
    elif a.cmd=='failures': print(json.dumps(ar.failures(a.limit),indent=2))
    elif a.cmd=='export': ar.export(a.hashes,a.destination)
    elif a.cmd=='sync': print(ar.sync(a.host,a.user,getpass.getpass(),a.folder))
    elif a.cmd=='gui':
        from desktop import launch
        launch(ar)
    return 0
if __name__=='__main__': raise SystemExit(main())
