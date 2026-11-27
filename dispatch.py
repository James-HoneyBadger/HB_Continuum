# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local read-only email archive. No network access except explicit sync."""
import shutil, argparse, hashlib, imaplib, sqlite3, ssl, json, os, tempfile
from pathlib import Path
from email import policy
from email.parser import BytesParser

__version__ = '0.3.0'

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
        CREATE TABLE IF NOT EXISTS origins(account TEXT, folder TEXT, validity TEXT, uid TEXT, hash TEXT NOT NULL REFERENCES messages(hash), PRIMARY KEY(account,folder,validity,uid));''')
    @staticmethod
    def _part_text(part):
        try:
            content=part.get_content()
        except (LookupError,UnicodeError,ValueError,TypeError):
            try: payload=part.get_payload(decode=True) or b''
            except Exception: return ''
            return payload.decode('utf-8','replace') if isinstance(payload,bytes) else str(payload)
        return content.decode('utf-8','replace') if isinstance(content,bytes) else content
    def ingest(self, raw, origin=None):
        if len(raw) > 64 * 1024 * 1024: raise ValueError('Message exceeds 64 MiB limit')
        digest = hashlib.sha256(raw).hexdigest(); target = self.raw / (digest+'.eml')
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=self.raw, delete=False) as f:
                f.write(raw); f.flush(); os.fsync(f.fileno()); tmp=f.name
            os.replace(tmp,target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError('Raw integrity mismatch')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        body='\n'.join(self._part_text(p) for p in msg.walk() if p.get_content_type()=='text/plain' and p.get_content_disposition()!='attachment')
        fields=[str(msg.get(k,'')) for k in ('Subject','From','Date','Message-ID','In-Reply-To')]
        with self.db:
            cur=self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?)',(digest,*fields,body))
            if cur.rowcount: self.db.execute('INSERT INTO search VALUES(?,?,?,?)',(digest,fields[0],fields[1],body))
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
    def verify(self):
        return [h for (h,) in self.db.execute('SELECT hash FROM messages') if not (p:=self.raw/(h+'.eml')).is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h]
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
                'origins':self.db.execute('SELECT count(*) FROM origins').fetchone()[0]}
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
                status,parts=m.uid('fetch',uid,'(BODY.PEEK[])')
                if status!='OK': raise RuntimeError('Fetch failed')
                payload=[p[1] for p in parts if isinstance(p,tuple)]
                if len(payload)!=1: raise RuntimeError('Unexpected fetch response')
                self.ingest(payload[0],origin); count+=1
                if prefs['batch_limit'] and count>=prefs['batch_limit']: break
            return count

def main():
    import getpass, sys
    p=argparse.ArgumentParser(); p.add_argument('--archive',default='~/.hb-dispatch'); p.add_argument('--version',action='version',version=f'%(prog)s {__version__}'); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('import'); q.add_argument('files',nargs='+'); q=sub.add_parser('search'); q.add_argument('query'); sub.add_parser('verify'); q=sub.add_parser('export'); q.add_argument('destination'); q.add_argument('hashes',nargs='+'); q=sub.add_parser('sync'); q.add_argument('host'); q.add_argument('user'); q.add_argument('--folder',default='INBOX'); sub.add_parser('gui'); q=sub.add_parser('facebook'); fb=q.add_subparsers(dest='fcmd',required=True); fp=fb.add_parser('preview'); fp.add_argument('paths',nargs='+'); fi=fb.add_parser('import'); fi.add_argument('paths',nargs='+'); fl=fb.add_parser('list'); fl.add_argument('--kind'); fl.add_argument('--actor'); fl.add_argument('--limit',type=int,default=100); fs=fb.add_parser('search'); fs.add_argument('query'); fs.add_argument('--limit',type=int,default=100); q=sub.add_parser('summarize'); su=q.add_subparsers(dest='scmd',required=True); sr=su.add_parser('run'); sr.add_argument('hashes',nargs='*'); sr.add_argument('--all',action='store_true'); sr.add_argument('--type',choices=('message','thread'),default='message'); sr.add_argument('--model'); sr.add_argument('--prompt-version'); sr.add_argument('--force',action='store_true'); sl=su.add_parser('list'); sl.add_argument('hash'); sd=su.add_parser('delete'); sd.add_argument('hash'); sd.add_argument('--type'); sd.add_argument('--model'); sd.add_argument('--prompt-version'); q=sub.add_parser('search-all'); q.add_argument('query'); q.add_argument('--limit',type=int,default=100); q.add_argument('--sources',default='email,facebook'); sub.add_parser('serve')
    a=p.parse_args(); ar=Archive(a.archive)
    if a.cmd=='import':
        for f in a.files: print(ar.ingest(Path(f).read_bytes()))
    elif a.cmd=='search': print(json.dumps(ar.find(a.query),indent=2))
    elif a.cmd=='search-all':
        from unified import search_unified
        sources=tuple(x.strip() for x in a.sources.split(',') if x.strip()) or ('email','facebook')
        print(json.dumps(search_unified(ar.root,a.query,a.limit,sources),indent=2))
    elif a.cmd=='verify':
        bad=ar.verify(); print(json.dumps(bad)); return int(bool(bad))
    elif a.cmd=='facebook':
        from facebook import preview, import_files
        if a.fcmd=='preview': print(json.dumps(preview(a.paths,ar.root),indent=2))
        elif a.fcmd=='import': print(json.dumps(import_files(a.paths,ar.root),indent=2))
        else:
            from catalog import Catalog
            c=Catalog(ar.root)
            try:
                rows=c.list_records('facebook',a.kind,a.actor,a.limit) if a.fcmd=='list' else c.search_records(a.query,'facebook',a.limit)
            finally:
                c.close()
            print(json.dumps([dict(zip(('record_id','source_key','record_kind','actor','occurred_at','body'),r)) for r in rows],indent=2))
    elif a.cmd=='summarize':
        from summarize import Summarizer, OllamaError
        s=Summarizer(ar.root)
        try:
            if a.scmd=='run':
                if not s.enabled(): print('summarize: AI is disabled; set ai.enabled and ai.backend=ollama in preferences', file=sys.stderr); return 1
                def progress(done,total,digest,status): print(f'[{done}/{total}] {digest[:12]} {status}', file=sys.stderr)
                try:
                    if a.all:
                        result=s.summarize_all(a.type, model=a.model, prompt_version=a.prompt_version, force=a.force, progress=progress)
                    else:
                        if not a.hashes: print('summarize: specify message hashes or --all', file=sys.stderr); return 2
                        result=s.summarize_batch(a.hashes, a.type, model=a.model, prompt_version=a.prompt_version, force=a.force, progress=progress)
                except OllamaError as e:
                    print(f'summarize: Ollama error: {e} (is Ollama running at {s.prefs["ai_endpoint"]}?)', file=sys.stderr); return 2
                print(json.dumps(result,indent=2))
            elif a.scmd=='list': print(json.dumps(s.list_summaries(a.hash),indent=2))
            elif a.scmd=='delete': print(json.dumps(s.delete(a.hash, a.type, a.model, a.prompt_version),indent=2))
        finally:
            s.close()
    elif a.cmd=='export': ar.export(a.hashes,a.destination)
    elif a.cmd=='sync': print(ar.sync(a.host,a.user,getpass.getpass(),a.folder))
    elif a.cmd=='serve':
        from ipc import IPCServer
        IPCServer(ar.root).serve()
    elif a.cmd=='gui':
        from desktop import launch
        launch(ar)
    return 0
if __name__=='__main__': raise SystemExit(main())
