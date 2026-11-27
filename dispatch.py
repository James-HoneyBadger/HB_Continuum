# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local read-only email archive. No network access except explicit sync."""
import shutil, argparse, hashlib, imaplib, sqlite3, ssl, json, os, tempfile
from pathlib import Path

__version__ = '0.3.0'

def valid_hash(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def verify_raw(conn, raw):
    """Return stored hashes whose original is missing, unsafe or altered."""
    bad=[]
    for h, in conn.execute('SELECT hash FROM messages'):
        if not valid_hash(h): bad.append(h); continue
        path=raw/(h+'.eml')
        try:
            if path.is_symlink() or not path.is_file(): bad.append(h); continue
            with path.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=h: bad.append(h)
        except OSError: bad.append(h)
    return bad

def timeline_rows(conn, sender=None, limit=100):
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
    return sorted(conn.execute(sql,params),key=key)[:max(1,min(int(limit),5000))]

def correspondent_counts(conn, limit=100):
    return conn.execute(
        "SELECT sender, count(*) FROM messages GROUP BY sender ORDER BY count(*) DESC, sender LIMIT ?",
        (max(1,min(int(limit),5000)),)).fetchall()

def diagnose(conn, raw):
    """Consistency report shared by the CLI and the desktop protocol."""
    checks=conn.execute('PRAGMA quick_check').fetchall()
    foreign=conn.execute('PRAGMA foreign_key_check').fetchall()
    hashes={h for h, in conn.execute('SELECT hash FROM messages')}
    indexed={h for h, in conn.execute('SELECT hash FROM search')}
    originals={p.stem for p in raw.glob('*.eml') if p.is_file()}
    duplicate=conn.execute('SELECT count(*) FROM search').fetchone()[0]-len(indexed)
    return {'sqlite_ok':checks==[('ok',)],'foreign_key_errors':len(foreign),'messages':len(hashes),
            'index_missing':sorted(hashes-indexed),'index_extra':sorted(indexed-hashes),
            'index_duplicate_rows':duplicate,'raw_missing':sorted(hashes-originals),
            'raw_unindexed':sorted(originals-hashes),'raw_invalid':verify_raw(conn,raw)}

class Archive:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve(); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.raw = self.root / 'raw'
        if self.raw.is_symlink() or (self.root / 'archive.sqlite3').is_symlink(): raise ValueError('Unsafe archive path')
        self.raw.mkdir(mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'archive.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=30000')
        from migrations import apply as migrate
        migrate(self.db, 'archive')
    def ingest(self, raw, origin=None):
        from sync_lock import sync_lock
        with sync_lock(self.root):
            return self._ingest(raw,origin)
    def _ingest(self, raw, origin=None):
        if len(raw) > 64 * 1024 * 1024: raise ValueError('Message exceeds 64 MiB limit')
        digest = hashlib.sha256(raw).hexdigest(); target = self.raw / (digest+'.eml')
        if target.is_symlink(): raise ValueError('Unsafe raw file')
        if not target.exists():
            tmp=None
            try:
                with tempfile.NamedTemporaryFile(dir=self.raw, delete=False) as f:
                    tmp=Path(f.name)
                    f.write(raw); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,target)
            finally:
                if tmp is not None: tmp.unlink(missing_ok=True)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError('Raw integrity mismatch')
        from mime_index import extract, index_text
        msg,body,attachments=extract(raw)
        fields=[str(msg.get(k,'')) for k in ('Subject','From','Date','Message-ID','In-Reply-To')]
        with self.db:
            cur=self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?)',(digest,*fields,body))
            if cur.rowcount:
                self.db.execute('INSERT INTO search VALUES(?,?,?,?)',(digest,fields[0],fields[1],index_text(body,attachments)))
                self.db.executemany('INSERT INTO attachment_index VALUES(?,?,?,?,?)',[(digest,*a) for a in attachments])
                self.db.execute('INSERT INTO extraction_versions VALUES(?,2)',(digest,))
            if origin:
                self.db.execute('INSERT OR IGNORE INTO origins VALUES(?,?,?,?,?)',(*origin,digest))
                if self.db.execute('SELECT hash FROM origins WHERE account=? AND folder=? AND validity=? AND uid=?',origin).fetchone()[0]!=digest: raise ValueError('Origin conflict')
        return digest
    def reindex(self, progress=None, cancel_event=None):
        """Repair derived index data from the preserved raw originals.

        Messages extracted by an older build, messages with a missing search
        row, and messages with duplicate search rows are re-extracted. Each
        message is verified against its raw original and re-indexed in its own
        transaction, so an interrupted or cancelled run keeps its progress.
        """
        from mime_index import extract, index_text
        from sync_lock import sync_lock
        count=0
        with sync_lock(self.root):
            pending=self.db.execute(
                'SELECT hash,subject,sender FROM messages '
                'WHERE hash NOT IN (SELECT hash FROM extraction_versions WHERE version=2) '
                'OR hash NOT IN (SELECT hash FROM search) '
                'OR hash IN (SELECT hash FROM search GROUP BY hash HAVING count(*)>1)').fetchall()
            total=len(pending)
            rowids={}
            for rowid,h in self.db.execute('SELECT rowid,hash FROM search'):
                rowids.setdefault(h,[]).append(rowid)
            for done,(h,subject,sender) in enumerate(pending,1):
                if cancel_event is not None and cancel_event.is_set(): break
                if not valid_hash(h): raise ValueError('Invalid stored message hash')
                source=self.raw/(h+'.eml')
                if source.is_symlink(): raise ValueError('Unsafe raw file')
                raw=source.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=h: raise ValueError('Raw integrity mismatch: '+h)
                _,body,attachments=extract(raw)
                with self.db:
                    self.db.execute('UPDATE messages SET body=? WHERE hash=?',(body,h))
                    self.db.executemany('DELETE FROM search WHERE rowid=?',[(rid,) for rid in rowids.get(h,[])])
                    self.db.execute('INSERT INTO search VALUES(?,?,?,?)',(h,subject,sender,index_text(body,attachments)))
                    self.db.execute('DELETE FROM attachment_index WHERE hash=?',(h,))
                    self.db.executemany('INSERT INTO attachment_index VALUES(?,?,?,?,?)',[(h,*a) for a in attachments])
                    self.db.execute('INSERT OR REPLACE INTO extraction_versions VALUES(?,2)',(h,))
                count+=1
                if progress is not None: progress(done,total,h,'reindexed')
        return count
    def attachments(self,h):
        return self.db.execute('SELECT filename,mime,length(content) FROM attachment_index WHERE hash=? ORDER BY part',(h,)).fetchall()
    def health(self):
        from sync_lock import sync_lock
        with sync_lock(self.root):
            return self._health()
    def _health(self):
        return diagnose(self.db,self.raw)
    def recover_orphans(self, progress=None, cancel_event=None):
        """Re-ingest valid raw originals left behind by an interrupted ingest.

        Only byte-verified files with a valid hash are recovered; no origin is
        invented, so a recovered message has no mailbox provenance. Altered,
        oversized and unreadable files are left in place for investigation.
        """
        from sync_lock import sync_lock
        recovered=[]
        with sync_lock(self.root):
            candidates=sorted(self.raw.glob('*.eml'))
            total=len(candidates)
            for done,path in enumerate(candidates,1):
                if cancel_event is not None and cancel_event.is_set(): break
                h=path.stem; status='skipped'
                try:
                    if (valid_hash(h) and not path.is_symlink() and path.is_file()
                            and not self.db.execute('SELECT 1 FROM messages WHERE hash=?',(h,)).fetchone()
                            and path.stat().st_size<=64*1024*1024):
                        raw=path.read_bytes()
                        if hashlib.sha256(raw).hexdigest()==h:
                            self._ingest(raw); recovered.append(h); status='recovered'
                except OSError: status='unreadable'
                if progress is not None: progress(done,total,h,status)
        return recovered
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
        return verify_raw(self.db,self.raw)
    def export(self, hashes, destination):
        dest=Path(destination)
        hashes=list(dict.fromkeys(hashes))
        if not hashes: raise ValueError('Select at least one message')
        for h in hashes:
            if not valid_hash(h):
                raise ValueError('Invalid message hash')
            if not self.db.execute('SELECT 1 FROM messages WHERE hash=?',(h,)).fetchone():
                raise ValueError('Unknown message')
        dest.mkdir(mode=0o700,parents=True,exist_ok=False)
        try:
            manifest=[]
            for h in hashes:
                source=self.raw/(h+'.eml')
                if source.is_symlink(): raise ValueError('Unsafe raw file')
                raw=source.read_bytes()
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
        return timeline_rows(self.db,sender,limit)
    def correspondents(self, limit=100):
        return correspondent_counts(self.db,limit)
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
                self._ingest(payload[0],origin); count+=1
                if prefs['batch_limit'] and count>=prefs['batch_limit']: break
            return count

def main(argv=None):
    import getpass, sys
    p=argparse.ArgumentParser(); p.add_argument('--archive',default='~/.hb-dispatch'); p.add_argument('--version',action='version',version=f'%(prog)s {__version__}'); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('import'); q.add_argument('files',nargs='+'); q=sub.add_parser('search'); q.add_argument('query'); sub.add_parser('verify'); q=sub.add_parser('export'); q.add_argument('destination'); q.add_argument('hashes',nargs='+'); q=sub.add_parser('sync'); q.add_argument('host'); q.add_argument('user'); q.add_argument('--folder',default='INBOX'); sub.add_parser('gui'); q=sub.add_parser('facebook'); fb=q.add_subparsers(dest='fcmd',required=True); fp=fb.add_parser('preview'); fp.add_argument('paths',nargs='+'); fi=fb.add_parser('import'); fi.add_argument('paths',nargs='+'); fl=fb.add_parser('list'); fl.add_argument('--kind'); fl.add_argument('--actor'); fl.add_argument('--limit',type=int,default=100); fs=fb.add_parser('search'); fs.add_argument('query'); fs.add_argument('--limit',type=int,default=100); q=sub.add_parser('summarize'); su=q.add_subparsers(dest='scmd',required=True); sr=su.add_parser('run'); sr.add_argument('hashes',nargs='*'); sr.add_argument('--all',action='store_true'); sr.add_argument('--type',choices=('message','thread'),default='message'); sr.add_argument('--model'); sr.add_argument('--prompt-version'); sr.add_argument('--force',action='store_true'); sl=su.add_parser('list'); sl.add_argument('hash'); sd=su.add_parser('delete'); sd.add_argument('hash'); sd.add_argument('--type'); sd.add_argument('--model'); sd.add_argument('--prompt-version'); q=sub.add_parser('search-all'); q.add_argument('query'); q.add_argument('--limit',type=int,default=100); q.add_argument('--sources',default='email,facebook'); sub.add_parser('serve'); sub.add_parser('health'); sub.add_parser('reindex'); sub.add_parser('recover-orphans'); q=sub.add_parser('backup'); q.add_argument('destination'); q=sub.add_parser('verify-backup'); q.add_argument('snapshot'); q=sub.add_parser('restore'); q.add_argument('snapshot'); q=sub.add_parser('schedule'); q.add_argument('args',nargs=argparse.REMAINDER); q=sub.add_parser('migrate'); q.add_argument('--dry-run',action='store_true'); q.add_argument('--no-snapshot',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='migrate':
        from migrations import report
        print(json.dumps(report(Path(a.archive).expanduser().resolve(),a.dry_run,not a.no_snapshot),indent=2))
        return 0
    if a.cmd in ('backup','verify-backup','restore'):
        import backup
        try:
            if a.cmd=='backup': result=backup.backup(a.archive,a.destination)
            elif a.cmd=='verify-backup': result=backup.validate_snapshot(Path(a.snapshot).expanduser())
            else: result=backup.restore(a.snapshot,a.archive)
        except (ValueError,FileExistsError,OSError,sqlite3.Error) as exc:
            print(f'{a.cmd}: {exc}',file=sys.stderr); return 1
        print(json.dumps(result)); return 0
    ar=Archive(a.archive)
    if a.cmd=='import':
        for f in a.files: print(ar.ingest(Path(f).read_bytes()))
    elif a.cmd=='reindex': print(ar.reindex())
    elif a.cmd=='recover-orphans': print(json.dumps(ar.recover_orphans()))
    elif a.cmd=='health':
        diagnosis=ar.health(); print(json.dumps(diagnosis,indent=2))
        return int(not diagnosis['sqlite_ok'] or any(diagnosis[k] for k in ('foreign_key_errors','index_missing','index_extra','index_duplicate_rows','raw_missing','raw_unindexed','raw_invalid')))
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
    elif a.cmd=='schedule':
        import schedule
        schedule.main(['--archive',str(ar.root),*a.args])
    elif a.cmd=='gui':
        from desktop import launch
        launch(ar)
    return 0
if __name__=='__main__': raise SystemExit(main())
