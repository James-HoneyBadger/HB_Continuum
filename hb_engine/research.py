# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""User-defined research overlays; original evidence is never modified."""
import csv, json, sqlite3, os
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone

COLUMNS=('subject','sender','date','message_id','reply_to','hash')
GROUPS=('sender','year','tag')
OPERATORS=('contains','equals','starts with')
FIELDS=('subject','sender','body','date')
TYPES=('text','number','date','choice','boolean')
JOURNAL_TITLE_MAX=200
JOURNAL_BODY_MAX=1_000_000
DRAFT_TITLE_MAX=200
DRAFT_NOTES_MAX=20_000
ADVANCED_QUERY_MAX=65_536
ADVANCED_QUERY_DESCRIPTION_MAX=4_000

def draft_title(value):
    if (not isinstance(value,str) or not value.strip() or len(value)>DRAFT_TITLE_MAX
            or any(ord(c)<32 for c in value)):
        raise ValueError('Report title must contain 1–200 printable characters')
    return value.strip()

def draft_notes(value):
    if value is None:
        return ''
    if not isinstance(value,str) or len(value)>DRAFT_NOTES_MAX:
        raise ValueError('Draft notes must be text up to 20,000 characters')
    return value

def namecheck(value):
    if not isinstance(value,str) or not value.strip() or len(value)>100 or any(ord(c)<32 for c in value):
        raise ValueError('Name must contain 1–100 printable characters')
    return value.strip()

def journal_title(value):
    if (not isinstance(value,str) or not value.strip() or len(value)>JOURNAL_TITLE_MAX
            or any(ord(c)<32 for c in value)):
        raise ValueError('Journal title must contain 1–200 printable characters')
    return value.strip()

def journal_body(value):
    if not isinstance(value,str) or len(value)>JOURNAL_BODY_MAX:
        raise ValueError('Journal body must be text up to 1,000,000 characters')
    return value

def journal_date(value):
    """Accept an ISO 8601 event date or None; the entry may be retrospective."""
    if value is None or value=='':
        return None
    if not isinstance(value,str) or len(value)>64:
        raise ValueError('Journal date must be an ISO 8601 string')
    try:
        datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise ValueError('Journal date must be an ISO 8601 string') from None
    return value

class Research:
    def __init__(self,archive):
        self.archive=archive
        self.db=sqlite3.connect(archive.root/'research.sqlite3',timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        from .migrations import apply as migrate
        migrate(self.db, 'research')
        self.db.execute("INSERT OR IGNORE INTO workspaces VALUES('General','Default research workspace')")
        self.db.commit()
    def close(self): self.db.close()
    def workspace(self,name,description=''):
        name=namecheck(name)
        with self.db:self.db.execute('INSERT INTO workspaces VALUES(?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description',(name,str(description)[:2000]))
    def save_search(self,workspace,name,query='',tag='',limit=1000):
        name=namecheck(name)
        if type(limit) is not int or not 1<=limit<=50000:raise ValueError('Limit must be 1–50000')
        if len(query)>4096 or len(tag)>100:raise ValueError('Search too long')
        with self.db:self.db.execute('INSERT OR REPLACE INTO searches VALUES(?,?,?,?,?)',(workspace,name,query,tag,limit))
    def results(self,workspace,name):
        row=self.db.execute('SELECT query,tag,limit_n FROM searches WHERE workspace=? AND name=?',(workspace,name)).fetchone()
        if row is None:raise ValueError('Unknown search')
        q,tag,limit=row
        # Filter by tag BEFORE applying result limit. Parameterized FTS; no user SQL.
        tagged=None if not tag else {h for h, in self.db.execute('SELECT DISTINCT hash FROM tags WHERE tag=?',(tag,))}
        if q:
            sql='SELECT m.hash,m.subject,m.sender,m.date,m.message_id,m.reply_to FROM search JOIN messages m ON m.hash=search.hash WHERE search MATCH ? ORDER BY m.rowid DESC'
            params=(q,)
        else:
            sql='SELECT hash,subject,sender,date,message_id,reply_to FROM messages ORDER BY rowid DESC';params=()
        rows=[]
        for r in self.archive.db.execute(sql,params):
            if tagged is None or r[0] in tagged:
                rows.append(dict(zip(('hash','subject','sender','date','message_id','reply_to'),r)))
                if len(rows)>=limit:break
        return rows
    def require_message(self,h):
        if not self.archive.db.execute('SELECT 1 FROM messages WHERE hash=?',(h,)).fetchone():raise ValueError('Unknown archived message')
    def tag(self,h,tag):
        self.require_message(h)
        with self.db:self.db.execute('INSERT OR IGNORE INTO tags VALUES(?,?,?)',(h,namecheck(tag),'manual'))
    def untag(self,h,tag):
        with self.db:self.db.execute("DELETE FROM tags WHERE hash=? AND tag=? AND source='manual'",(h,tag))
    def save_rule(self,name,field,operator,value,tag,enabled=True):
        name=namecheck(name);tag=namecheck(tag)
        if field not in FIELDS or operator not in OPERATORS or not value or len(value)>4096:raise ValueError('Invalid rule')
        with self.db:self.db.execute('INSERT OR REPLACE INTO rules VALUES(?,?,?,?,?,?)',(name,field,operator,value,tag,int(bool(enabled))))
    def apply_rules(self):
        rules=self.db.execute('SELECT * FROM rules WHERE enabled=1').fetchall()
        compiled=[(n,FIELDS.index(f)+1,o,v.casefold(),t) for n,f,o,v,t,e in rules]
        count=0
        with self.db:
            self.db.execute("DELETE FROM tags WHERE source LIKE 'rule:%'")
            for row in self.archive.db.execute('SELECT hash,subject,sender,body,date FROM messages'):
                for n,i,o,v,t in compiled:
                    s=(row[i] or '').casefold()
                    match=v in s if o=='contains' else s==v if o=='equals' else s.startswith(v)
                    if match:
                        self.db.execute('INSERT OR IGNORE INTO tags VALUES(?,?,?)',(row[0],t,'rule:'+n));count+=1
        return count
    def define_field(self,name,kind,choices=()):
        name=namecheck(name)
        if kind not in TYPES:raise ValueError('Invalid field type')
        if kind=='choice' and (not choices or len(set(choices))!=len(choices)):raise ValueError('Provide unique choices')
        encoded=json.dumps(list(choices) if kind=='choice' else [])
        old=self.db.execute('SELECT type,choices FROM fields WHERE name=?',(name,)).fetchone()
        if old and old!=(kind,encoded) and self.db.execute('SELECT 1 FROM metadata WHERE field=? LIMIT 1',(name,)).fetchone():raise ValueError('Cannot change a populated field definition')
        with self.db:self.db.execute('INSERT INTO fields VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET type=excluded.type,choices=excluded.choices',(name,kind,encoded))
    def set_metadata(self,h,field,value):
        self.require_message(h)
        row=self.db.execute('SELECT type,choices FROM fields WHERE name=?',(field,)).fetchone()
        if row is None:raise ValueError('Unknown field')
        kind,choices=row
        if not isinstance(value,str) or len(value)>4096:raise ValueError('Invalid value')
        if kind=='number':
            from decimal import Decimal
            if not Decimal(value).is_finite():raise ValueError('Number must be finite')
        elif kind=='date':
            from datetime import date
            date.fromisoformat(value)
        elif kind=='choice' and value not in json.loads(choices):raise ValueError('Invalid choice')
        elif kind=='boolean' and value not in ('true','false'):raise ValueError('Use true or false')
        with self.db:self.db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?,?)',(h,field,value))
    @staticmethod
    def _advanced_sources(sources):
        if isinstance(sources,str):
            sources=[part.strip() for part in sources.split(',') if part.strip()]
        if not isinstance(sources,(list,tuple)) or not sources:
            raise ValueError('Sources must be email and/or facebook')
        values=list(dict.fromkeys(sources))
        if any(value not in ('email','facebook') for value in values):
            raise ValueError('Sources must be email and/or facebook')
        return ','.join(values)
    @staticmethod
    def _advanced_id(query_id):
        if type(query_id) is not int or query_id<1:
            raise ValueError('Invalid advanced query id')
        return query_id
    def _advanced_row(self,query_id):
        row=self.db.execute(
            'SELECT id,workspace,name,description,sources,created_at,updated_at '
            'FROM advanced_queries WHERE id=?',(self._advanced_id(query_id),)).fetchone()
        if row is None: raise ValueError('Unknown advanced query')
        return row
    @staticmethod
    def _advanced_summary(row):
        keys=('id','workspace','name','description','sources','created_at','updated_at')
        result=dict(zip(keys,row))
        result['sources']=[value for value in result['sources'].split(',') if value]
        return result
    def advanced_query_list(self,workspace=None):
        sql=('SELECT id,workspace,name,description,sources,created_at,updated_at '
             'FROM advanced_queries')
        params=()
        if workspace:
            sql+=' WHERE workspace=?'; params=(workspace,)
        sql+=' ORDER BY workspace,name'
        return [self._advanced_summary(row) for row in self.db.execute(sql,params)]
    def advanced_query_get(self,query_id):
        row=self._advanced_row(query_id)
        result=self._advanced_summary(row)
        stored=self.db.execute(
            'SELECT query_json FROM advanced_queries WHERE id=?',(result['id'],)).fetchone()[0]
        try:
            result['tree']=json.loads(stored)
        except (TypeError,ValueError):
            raise ValueError('Stored advanced query is not valid JSON') from None
        return result
    def advanced_query_save(self,workspace,name,description,tree,sources=('email','facebook')):
        name=namecheck(name)
        if not isinstance(description,str) or len(description)>ADVANCED_QUERY_DESCRIPTION_MAX:
            raise ValueError('Description must be text up to 4,000 characters')
        if not isinstance(tree,dict) or not tree:
            raise ValueError('Query tree must be a non-empty object')
        if tree.get('type')!='group':
            raise ValueError('Query tree root must be a group')
        if not self.db.execute('SELECT 1 FROM workspaces WHERE name=?',(workspace,)).fetchone():
            raise ValueError('Unknown workspace')
        source_text=self._advanced_sources(sources)
        try:
            query_json=json.dumps(tree,ensure_ascii=False,separators=(',',':'),sort_keys=True)
        except (TypeError,ValueError):
            raise ValueError('Query tree must be JSON-serializable') from None
        if len(query_json)>ADVANCED_QUERY_MAX:
            raise ValueError('Query tree exceeds the 65,536 character limit')
        now=datetime.now(timezone.utc).isoformat(timespec='seconds')
        with self.db:
            row=self.db.execute(
                'SELECT id FROM advanced_queries WHERE workspace=? AND name=?',
                (workspace,name)).fetchone()
            if row:
                query_id=row[0]
                self.db.execute(
                    'UPDATE advanced_queries SET description=?,query_json=?,sources=?,'
                    'updated_at=? WHERE id=?',
                    (description,query_json,source_text,now,query_id))
            else:
                query_id=self.db.execute(
                    'INSERT INTO advanced_queries(workspace,name,description,query_json,'
                    'sources,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                    (workspace,name,description,query_json,source_text,now,now)).lastrowid
        return self.advanced_query_get(query_id)
    def advanced_query_delete(self,query_id):
        with self.db:
            cursor=self.db.execute(
                'DELETE FROM advanced_queries WHERE id=?',(self._advanced_id(query_id),))
        if not cursor.rowcount: raise ValueError('Unknown advanced query')
        return {'deleted': query_id}
    def save_report(self,name,workspace,search,columns,group_by=''):
        name=namecheck(name)
        if not columns or len(set(columns))!=len(columns) or any(c not in COLUMNS for c in columns):raise ValueError('Invalid report columns')
        if group_by and group_by not in GROUPS:raise ValueError('Invalid grouping')
        if not self.db.execute('SELECT 1 FROM searches WHERE workspace=? AND name=?',(workspace,search)).fetchone():raise ValueError('Unknown search')
        with self.db:self.db.execute('INSERT OR REPLACE INTO reports VALUES(?,?,?,?,?)',(name,workspace,search,json.dumps(columns),group_by))
    def report(self,name):
        row=self.db.execute('SELECT workspace,search,columns,group_by FROM reports WHERE name=?',(name,)).fetchone()
        if row is None:raise ValueError('Unknown report')
        w,s,cols,group=row;rows=self.results(w,s)
        if group:
            from collections import Counter
            from email.utils import parsedate_to_datetime
            counts=Counter()
            for r in rows:
                if group=='tag':
                    keys=[x[0] for x in self.db.execute('SELECT DISTINCT tag FROM tags WHERE hash=?',(r['hash'],))] or ['(untagged)']
                elif group=='year':
                    try:keys=[str(parsedate_to_datetime(r['date']).year)]
                    except (TypeError,ValueError,OverflowError):keys=['(unknown)']
                else:keys=[r['sender'] or '(unknown)']
                counts.update(keys)
            return [group,'count'],[dict(zip((group,'count'),x)) for x in counts.most_common()]
        columns=json.loads(cols)
        return columns,[{k:r[k] for k in columns} for r in rows]
    def _journal_clock(self):
        return datetime.now(timezone.utc).isoformat(timespec='seconds')
    def _journal_row(self,entry_id):
        if type(entry_id) is not int or entry_id<1: raise ValueError('Invalid journal entry id')
        row=self.db.execute(
            'SELECT id,title,body,event_date,created_at,updated_at,revision,deleted_at '
            'FROM journal_entries WHERE id=?',(entry_id,)).fetchone()
        if row is None: raise ValueError('Unknown journal entry')
        return row
    def journal_list(self,limit=100,include_deleted=False):
        if type(limit) is not int or not 1<=limit<=500: raise ValueError('Limit must be 1–500')
        sql='SELECT id,title,event_date,created_at,updated_at,revision,deleted_at FROM journal_entries'
        if not include_deleted: sql+=' WHERE deleted_at IS NULL'
        sql+=' ORDER BY COALESCE(event_date,substr(created_at,1,10)) DESC, id DESC LIMIT ?'
        keys=('id','title','event_date','created_at','updated_at','revision','deleted_at')
        return [dict(zip(keys,row)) for row in self.db.execute(sql,(limit,))]
    def journal_get(self,entry_id):
        entry=dict(zip(('id','title','body','event_date','created_at','updated_at','revision','deleted_at'),
                       self._journal_row(entry_id)))
        entry['revisions']=[dict(zip(('revision','title','body','event_date','recorded_at'),row))
                            for row in self.db.execute(
                                'SELECT revision,title,body,event_date,recorded_at '
                                'FROM journal_revisions WHERE entry_id=? ORDER BY revision DESC',
                                (entry_id,))]
        return entry
    def journal_create(self,title,body='',event_date=None):
        title=journal_title(title); body=journal_body(body); event_date=journal_date(event_date)
        now=self._journal_clock()
        with self.db:
            entry_id=self.db.execute(
                'INSERT INTO journal_entries(title,body,event_date,created_at,updated_at,revision) '
                'VALUES(?,?,?,?,?,1)',(title,body,event_date,now,now)).lastrowid
            self.db.execute(
                'INSERT INTO journal_revisions(entry_id,revision,title,body,event_date,recorded_at) '
                'VALUES(?,?,?,?,?,?)',(entry_id,1,title,body,event_date,now))
        return self.journal_get(entry_id)
    def journal_update(self,entry_id,title,body,event_date=None):
        current=self._journal_row(entry_id)
        title=journal_title(title); body=journal_body(body); event_date=journal_date(event_date)
        if (title,body,event_date)==(current[1],current[2],current[3]):
            return self.journal_get(entry_id)
        now=self._journal_clock(); revision=current[6]+1
        with self.db:
            self.db.execute(
                'UPDATE journal_entries SET title=?,body=?,event_date=?,updated_at=?,revision=? '
                'WHERE id=?',(title,body,event_date,now,revision,entry_id))
            self.db.execute(
                'INSERT INTO journal_revisions(entry_id,revision,title,body,event_date,recorded_at) '
                'VALUES(?,?,?,?,?,?)',(entry_id,revision,title,body,event_date,now))
        return self.journal_get(entry_id)
    def journal_delete(self,entry_id):
        """Soft-delete an entry; its revisions stay available for inspection."""
        self._journal_row(entry_id)
        now=self._journal_clock()
        with self.db:
            self.db.execute(
                'UPDATE journal_entries SET deleted_at=COALESCE(deleted_at,?),updated_at=? '
                'WHERE id=?',(now,now,entry_id))
        return self.journal_get(entry_id)
    def journal_restore(self,entry_id):
        self._journal_row(entry_id)
        now=self._journal_clock()
        with self.db:
            self.db.execute('UPDATE journal_entries SET deleted_at=NULL,updated_at=? WHERE id=?',
                            (now,entry_id))
        return self.journal_get(entry_id)
    def _collection_clock(self):
        return datetime.now(timezone.utc).isoformat(timespec='seconds')
    def _collection_row(self,collection_id):
        if type(collection_id) is not int or collection_id<1:
            raise ValueError('Invalid collection id')
        row=self.db.execute(
            'SELECT id,workspace,name,description,created_at,updated_at '
            'FROM collections WHERE id=?',(collection_id,)).fetchone()
        if row is None: raise ValueError('Unknown collection')
        return row
    def collection_list(self,workspace=None):
        sql=('SELECT c.id,c.workspace,c.name,c.description,c.created_at,c.updated_at,'
             'count(i.item_id) FROM collections c '
             'LEFT JOIN collection_items i ON i.collection_id=c.id')
        params=()
        if workspace:
            sql+=' WHERE c.workspace=?'; params=(workspace,)
        sql+=' GROUP BY c.id ORDER BY c.name'
        keys=('id','workspace','name','description','created_at','updated_at','item_count')
        return [dict(zip(keys,row)) for row in self.db.execute(sql,params)]
    def collection_create(self,workspace,name,description=''):
        name=namecheck(name)
        if not isinstance(description,str) or len(description)>4000:
            raise ValueError('Description must be text up to 4000 characters')
        if not self.db.execute('SELECT 1 FROM workspaces WHERE name=?',(workspace,)).fetchone():
            raise ValueError('Unknown workspace')
        now=self._collection_clock()
        try:
            with self.db:
                collection_id=self.db.execute(
                    'INSERT INTO collections(workspace,name,description,created_at,updated_at) '
                    'VALUES(?,?,?,?,?)',(workspace,name,description,now,now)).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError('A collection with that name already exists in this workspace') from None
        return self.collection_get(collection_id)
    def _collection_items(self,collection_id):
        rows=self.db.execute(
            'SELECT item_type,item_id,note,added_at FROM collection_items '
            'WHERE collection_id=? ORDER BY added_at,item_id',(collection_id,)).fetchall()
        items=[]; catalog=None
        try:
            for item_type,item_id,note,added_at in rows:
                title=actor=date=kind=''; exists=False
                if item_type=='email':
                    found=self.archive.db.execute(
                        'SELECT subject,sender,date FROM messages WHERE hash=?',
                        (item_id,)).fetchone()
                    if found:
                        title,actor,date=found[0] or '',found[1] or '',found[2] or ''
                        exists=True
                    kind='message'
                else:
                    if catalog is None:
                        path=self.archive.root/'catalog.sqlite3'
                        if path.is_file():
                            catalog=sqlite3.connect(str(path),timeout=30)
                            catalog.execute('PRAGMA query_only=ON')
                    if catalog is not None:
                        found=catalog.execute(
                            'SELECT record_kind,actor,occurred_at FROM records WHERE record_id=?',
                            (item_id,)).fetchone()
                        if found:
                            kind,actor,date=found[0] or '',found[1] or '',found[2] or ''
                            exists=True
                items.append({'item_type':item_type,'item_id':item_id,'note':note or '',
                              'added_at':added_at,'title':title,'actor':actor,'date':date,
                              'kind':kind,'exists':exists})
        finally:
            if catalog is not None: catalog.close()
        return items
    def collection_get(self,collection_id):
        row=self._collection_row(collection_id)
        collection=dict(zip(('id','workspace','name','description','created_at','updated_at'),row))
        collection['items']=self._collection_items(collection_id)
        collection['item_count']=len(collection['items'])
        return collection
    def _require_collection_item(self,item_type,item_id):
        if not isinstance(item_id,str) or not item_id:
            raise ValueError('Invalid item id')
        if item_type=='email':
            if not self.archive.db.execute('SELECT 1 FROM messages WHERE hash=?',(item_id,)).fetchone():
                raise ValueError('Unknown archived message')
            return
        if item_type=='catalog':
            path=self.archive.root/'catalog.sqlite3'
            if not path.is_file(): raise ValueError('Unknown catalog record')
            with closing(sqlite3.connect(str(path),timeout=30)) as conn:
                conn.execute('PRAGMA query_only=ON')
                if not conn.execute('SELECT 1 FROM records WHERE record_id=?',(item_id,)).fetchone():
                    raise ValueError('Unknown catalog record')
            return
        raise ValueError('item_type must be email or catalog')
    def collection_add(self,collection_id,item_type,item_id,note=None):
        self._collection_row(collection_id)
        self._require_collection_item(item_type,item_id)
        if note is not None and (not isinstance(note,str) or len(note)>2000):
            raise ValueError('Note must be text up to 2000 characters')
        now=self._collection_clock()
        with self.db:
            self.db.execute(
                'INSERT INTO collection_items(collection_id,item_type,item_id,note,added_at) '
                'VALUES(?,?,?,?,?) ON CONFLICT(collection_id,item_type,item_id) '
                'DO UPDATE SET note=excluded.note',
                (collection_id,item_type,item_id,note,now))
            self.db.execute('UPDATE collections SET updated_at=? WHERE id=?',(now,collection_id))
        return self.collection_get(collection_id)
    def collection_remove(self,collection_id,item_type,item_id):
        self._collection_row(collection_id)
        now=self._collection_clock()
        with self.db:
            self.db.execute(
                'DELETE FROM collection_items WHERE collection_id=? AND item_type=? AND item_id=?',
                (collection_id,item_type,item_id))
            self.db.execute('UPDATE collections SET updated_at=? WHERE id=?',(now,collection_id))
        return self.collection_get(collection_id)
    def collection_delete(self,collection_id):
        self._collection_row(collection_id)
        with self.db:
            self.db.execute('DELETE FROM collections WHERE id=?',(collection_id,))
        return {'deleted':True,'id':collection_id}
    def _draft_row(self,draft_id):
        if type(draft_id) is not int or draft_id<1:
            raise ValueError('Invalid report draft id')
        row=self.db.execute(
            'SELECT id,collection_id,title,notes,created_at,updated_at '
            'FROM report_drafts WHERE id=?',(draft_id,)).fetchone()
        if row is None: raise ValueError('Unknown report draft')
        return row
    def draft_list(self,collection_id=None):
        keys=('id','collection_id','title','notes','created_at','updated_at')
        if collection_id is not None:
            self._collection_row(collection_id)
            sql=('SELECT id,collection_id,title,notes,created_at,updated_at '
                 'FROM report_drafts WHERE collection_id=? '
                 'ORDER BY updated_at DESC, id DESC')
            rows=self.db.execute(sql,(collection_id,))
        else:
            rows=self.db.execute(
                'SELECT id,collection_id,title,notes,created_at,updated_at '
                'FROM report_drafts ORDER BY updated_at DESC, id DESC')
        return [dict(zip(keys,row)) for row in rows]
    def draft_create(self,collection_id,title,notes=''):
        self._collection_row(collection_id)
        title=draft_title(title); notes=draft_notes(notes)
        now=self._collection_clock()
        with self.db:
            draft_id=self.db.execute(
                'INSERT INTO report_drafts(collection_id,title,notes,created_at,updated_at) '
                'VALUES(?,?,?,?,?)',(collection_id,title,notes,now,now)).lastrowid
        return self.draft_get(draft_id)
    def draft_update(self,draft_id,title,notes=''):
        self._draft_row(draft_id)
        title=draft_title(title); notes=draft_notes(notes)
        now=self._collection_clock()
        with self.db:
            self.db.execute(
                'UPDATE report_drafts SET title=?,notes=?,updated_at=? WHERE id=?',
                (title,notes,now,draft_id))
        return self.draft_get(draft_id)
    def draft_get(self,draft_id):
        row=self._draft_row(draft_id)
        draft=dict(zip(('id','collection_id','title','notes','created_at','updated_at'),row))
        draft['collection']=self.collection_get(row[1])
        return draft
    def draft_delete(self,draft_id):
        self._draft_row(draft_id)
        with self.db:
            self.db.execute('DELETE FROM report_drafts WHERE id=?',(draft_id,))
        return {'deleted':True,'id':draft_id}
    def export_report(self,name,path):
        cols,rows=self.report(name)
        def safe(v):
            # Prevent spreadsheet formula execution from untrusted mail headers.
            return "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else v
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',newline='',encoding='utf-8') as f:
            out=csv.DictWriter(f,fieldnames=cols);out.writeheader()
            out.writerows({k:safe(v) for k,v in r.items()} for r in rows)
