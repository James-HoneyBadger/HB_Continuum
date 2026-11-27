# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""User-defined research overlays; original evidence is never modified."""
import csv, json, sqlite3, os
from pathlib import Path
from datetime import datetime, timezone

COLUMNS=('subject','sender','date','message_id','reply_to','hash')
GROUPS=('sender','year','tag')
OPERATORS=('contains','equals','starts with')
FIELDS=('subject','sender','body','date')
TYPES=('text','number','date','choice','boolean')

def namecheck(value):
    if not isinstance(value,str) or not value.strip() or len(value)>100 or any(ord(c)<32 for c in value):
        raise ValueError('Name must contain 1–100 printable characters')
    return value.strip()

class Research:
    def __init__(self,archive):
        self.archive=archive
        self.db=sqlite3.connect(archive.root/'research.sqlite3',timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        from migrations import apply as migrate
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
    def export_report(self,name,path):
        cols,rows=self.report(name)
        def safe(v):
            # Prevent spreadsheet formula execution from untrusted mail headers.
            return "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else v
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',newline='',encoding='utf-8') as f:
            out=csv.DictWriter(f,fieldnames=cols);out.writeheader()
            out.writerows({k:safe(v) for k,v in r.items()} for r in rows)
