# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Local correspondence workstation. Plain text only; no remote rendering."""
def launch(archive):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from pathlib import Path
    from preferences import load
    prefs=load(archive.root)
    root=tk.Tk()
    root.title('HB Dispatch — Correspondence Workstation')
    root.geometry(f"{prefs['window_width']}x{prefs['window_height']}")
    style=ttk.Style(root)
    if prefs['theme']!='System':
        style.theme_use('clam')
        bg,fg=('#24272b','#ededed') if prefs['theme']=='Dark' else ('#f4f5f6','#202124')
        style.configure('.',background=bg,foreground=fg)
        style.configure('Treeview',fieldbackground=bg,background=bg,foreground=fg)
        style.configure('TEntry',fieldbackground=bg,foreground=fg)
        root.configure(bg=bg)
    root.minsize(720,480)
    toolbar=ttk.Frame(root,padding=10)
    toolbar.pack(fill='x')
    query=ttk.Entry(toolbar)
    query.pack(side='left',fill='x',expand=True)
    filters=ttk.Frame(root,padding=(10,0))
    filters.pack(fill='x')
    ttk.Label(filters,text='Sender').pack(side='left')
    sender_filter=ttk.Entry(filters,width=20); sender_filter.pack(side='left',padx=(3,10))
    ttk.Label(filters,text='To/cc').pack(side='left')
    recipient_filter=ttk.Entry(filters,width=20); recipient_filter.pack(side='left',padx=(3,10))
    ttk.Label(filters,text='From').pack(side='left')
    after_filter=ttk.Entry(filters,width=11); after_filter.pack(side='left',padx=(3,10))
    ttk.Label(filters,text='To').pack(side='left')
    before_filter=ttk.Entry(filters,width=11); before_filter.pack(side='left',padx=(3,10))
    ttk.Label(filters,text='Attachment').pack(side='left')
    attachment_filter=ttk.Entry(filters,width=16); attachment_filter.pack(side='left',padx=(3,10))
    ttk.Label(filters,text='Dates are ISO, for example 2024-01-31').pack(side='left')
    def filter_values():
        return (sender_filter.get().strip() or None,
                after_filter.get().strip() or None,
                before_filter.get().strip() or None,
                recipient_filter.get().strip() or None,
                attachment_filter.get().strip() or None)
    status=tk.StringVar()
    pane=ttk.Panedwindow(root,orient=prefs['layout'])
    pane.pack(fill='both',expand=True,padx=10,pady=5)
    listing=ttk.Frame(pane)
    rows=ttk.Treeview(listing,columns=('subject','sender'),show='headings',selectmode='extended')
    rows.heading('subject',text='Subject')
    rows.heading('sender',text='Sender')
    rows.column('subject',width=prefs['subject_width'])
    rows.column('sender',width=prefs['sender_width'])
    scroll=ttk.Scrollbar(listing,orient='vertical',command=rows.yview)
    rows.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y')
    rows.pack(fill='both',expand=True)
    pane.add(listing,weight=2)
    reader=ttk.Frame(pane)
    family={'System':'TkDefaultFont','Monospace':'TkFixedFont','Serif':'Times'}[prefs['font_family']]
    body=tk.Text(reader,wrap=prefs['wrap'],font=(family,prefs['font_size']),state='disabled',padx=12,pady=10)
    if prefs['theme']!='System':body.configure(background=bg,foreground=fg,insertbackground=fg)
    scroll2=ttk.Scrollbar(reader,orient='vertical',command=body.yview)
    body.configure(yscrollcommand=scroll2.set)
    scroll2.pack(side='right',fill='y')
    body.pack(fill='both',expand=True)
    pane.add(reader,weight=3)
    ttk.Label(root,textvariable=status,padding=10).pack(fill='x')
    def display(text):
        body.configure(state='normal')
        body.delete('1.0','end')
        body.insert('1.0',text)
        body.configure(state='disabled')
    def search(*_):
        try:
            term=query.get().strip()
            if term and prefs['search_mode']=='Exact phrase': term='"'+term.replace('"','""')+'"'
            sender,after,before,recipient,attachment=filter_values()
            hits=(archive.find(term,prefs['search_limit'],sender,after,before,recipient,attachment)
                  if any((term,sender,after,before,recipient,attachment)) else archive.recent(prefs['recent_limit']))
            rows.delete(*rows.get_children())
            display('')
            for h,s,f in hits: rows.insert('', 'end',iid=h,values=(s,f))
            stats=archive.stats()
            status.set(f"{len(hits)} shown  |  {stats['messages']} archived messages  |  {stats['origins']} mailbox origins  |  {stats['attachments']} attachments")
        except Exception as e: messagebox.showerror('Search',str(e))
    def select(*_):
        selection=rows.selection()
        if not selection: return
        try:
            h=selection[0]
            data=archive.details(h)
            keys=('subject','sender','recipient','cc','date','message_id','reply_to') if prefs['show_message_ids'] else ('subject','sender','recipient','cc','date')
            header='\n'.join(f"{k}: {data[k]}" for k in keys if data[k])
            files=archive.attachments(h)
            listing=('\n\nAttachments:\n'+'\n'.join(f"  {name}  ({ctype}, {size} bytes)\n  SHA-256: {sha}" for name,ctype,size,sha in files)) if files else ''
            places=archive.provenance(h)
            provenance=('\n\nProvenance:\n'+'\n'.join(
                f"  {p['account']} / {p['folder']}  UID {p['uid']}  acquired {p['first_seen'] or 'unknown'}" for p in places)) if places else ''
            display(header+('\nSHA-256: '+h if prefs['show_hash'] else '')+listing+provenance+'\n\n'+data['body'])
        except Exception as e: messagebox.showerror('Message',str(e))
    def show_thread():
        selected=rows.selection()
        if not selected: return messagebox.showinfo('Conversation','Select a message first.')
        try:
            messages=archive.thread(selected[0])
            display('\n\n'.join(
                f"{m['date']} | {m['sender']}\n{m['subject']}\nSHA-256: {m['sha256']}\n\n{m['body']}"
                for m in messages))
        except Exception as e: messagebox.showerror('Conversation',str(e))
    def show_timeline():
        try:
            hits=archive.timeline(limit=prefs['timeline_limit'])
            display('\n\n'.join(f"{date or 'Unknown date'} | {sender}\n{subject}\nSHA-256: {h}" for h,subject,sender,date in hits))
            status.set(f'{len(hits)} messages in timeline; dates are sender-declared.')
        except Exception as e: messagebox.showerror('Timeline',str(e))
    def show_correspondents():
        try:
            display('\n'.join(f'{count:>6}  {sender or "(unknown sender)"}' for sender,count in archive.correspondents(prefs['correspondent_limit'])))
        except Exception as e: messagebox.showerror('Correspondents',str(e))
    def import_files():
        try:
            for f in filedialog.askopenfilenames(initialdir=prefs['import_directory'] or None,filetypes=[('Email','*.eml')]):
                path=Path(f)
                if path.stat().st_size>64*1024*1024: raise ValueError('Message exceeds 64 MiB limit')
                archive.ingest(path.read_bytes())
            search()
        except Exception as e: messagebox.showerror('Import',str(e))
    def verify():
        try:
            bad=archive.verify(); bad_files=archive.verify_attachments()
            if bad or bad_files:
                messagebox.showwarning('Integrity check',
                    f'{len(bad)} messages and {len(bad_files)} attachment files failed verification.\n'
                    +'\n'.join(bad[:10]+bad_files[:10]))
            else: messagebox.showinfo('Integrity check','All indexed originals and attachment files match their stored hashes.')
        except Exception as e: messagebox.showerror('Integrity check',str(e))
    def repair():
        if not messagebox.askyesno('Repair archive','Rebuild metadata, search and attachment records from the preserved raw files? Original messages are not modified.'): return
        try:
            rebuilt=archive.reindex(); search()
            messagebox.showinfo('Repair complete',f'{rebuilt} messages rebuilt from stored raw files.')
        except Exception as e: messagebox.showerror('Repair archive',str(e))
    def sync_failures():
        try:
            failed=archive.failures()
            if not failed: return messagebox.showinfo('Synchronization failures','No messages have failed to archive.')
            display('\n\n'.join(f"{account} / {folder} / UID {uid}\nattempts: {attempts}  last seen: {last_seen}\n{error}"
                                for account,folder,validity,uid,attempts,error,last_seen in failed))
            status.set(f'{len(failed)} mailbox messages could not be archived; they remain on the server.')
        except Exception as e: messagebox.showerror('Synchronization failures',str(e))
    def sync_log():
        try:
            entries=archive.sync_log()
            if not entries: return messagebox.showinfo('Synchronization log','No synchronization attempts are recorded yet.')
            display('\n\n'.join(f"{account} / {folder}\n{started} to {finished}  |  {archived} archived"
                                  + (f"\n{error}" if error else '') for account,folder,started,finished,archived,error in entries))
            status.set(f'{len(entries)} recent synchronization attempts. The log records counts and errors, never credentials or message content.')
        except Exception as e: messagebox.showerror('Synchronization log',str(e))
    def export_mbox():
        selected=rows.selection()
        if not selected: return messagebox.showinfo('Export mbox','Select one or more messages first.')
        target=filedialog.asksaveasfilename(initialdir=prefs['export_directory'] or None,defaultextension='.mbox',
                                            filetypes=[('Mailbox','*.mbox')],title='Save selected messages as an mbox file')
        if not target: return
        if Path(target).exists():
            return messagebox.showerror('Export mbox','That file already exists; choose a new name so nothing is overwritten.')
        try:
            archive.export_mbox(selected,target)
            messagebox.showinfo('Export complete',f'{len(selected)} messages written to {target}')
        except Exception as e: messagebox.showerror('Export mbox',str(e))
    def save_attachments():
        selected=rows.selection()
        if not selected: return messagebox.showinfo('Attachments','Select one or more messages first.')
        parent=filedialog.askdirectory(initialdir=prefs['export_directory'] or None,title='Choose a folder for attachment copies')
        if not parent: return
        import os
        saved=skipped=0
        try:
            for h in selected:
                for name,ctype,size,sha in archive.attachments(h):
                    target=Path(parent)/(Path(name).name or 'attachment')
                    if target.exists(): skipped+=1; continue
                    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as output:
                        output.write(archive.attachment_bytes(sha))
                    saved+=1
            messagebox.showinfo('Attachments',f'{saved} files saved, {skipped} skipped because a file of that name already exists.')
        except Exception as e: messagebox.showerror('Attachments',str(e))
    def export():
        selected=rows.selection()
        if not selected: return messagebox.showinfo('Export','Select one or more messages first.')
        parent=filedialog.askdirectory(initialdir=prefs['export_directory'] or None,title='Choose parent folder for evidence package')
        if not parent: return
        from datetime import datetime,timezone
        dest=Path(parent)/('evidence-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        try:
            archive.export(selected,dest)
            messagebox.showinfo('Export complete',str(dest))
        except Exception as e: messagebox.showerror('Export',str(e))
    for label,fn in [('Search',search),('Import EML',import_files),('Verify',verify),('Repair archive',repair),
                     ('Save attachments',save_attachments),('Export selected',export),('Export mbox',export_mbox)]:
        ttk.Button(toolbar,text=label,command=fn).pack(side='left',padx=3)
    analysis_bar=ttk.Frame(root,padding=(10,0))
    analysis_bar.pack(fill='x',before=pane)
    for label,fn in [('Conversation',show_thread),('Timeline',show_timeline),('Correspondents',show_correspondents),
                     ('Sync failures',sync_failures),('Sync log',sync_log)]:
        ttk.Button(analysis_bar,text=label,command=fn).pack(side='left',padx=3)
    def scheduling():
        from schedule_ui import launch as launch_schedule
        launch_schedule(archive.root.resolve(), root)
    ttk.Button(analysis_bar,text='Synchronization center',command=scheduling).pack(side='left',padx=3)
    def configure():
        from preferences_ui import launch as launch_preferences
        launch_preferences(archive.root,root)
    ttk.Button(analysis_bar,text='Configuration center',command=configure).pack(side='left',padx=3)
    if prefs['startup_view']=='Saved query':query.insert(0,prefs['startup_query'])
    if prefs['verify_on_start']:root.after(100,verify)
    def research_workbench():
        from research_ui import launch as launch_research
        launch_research(archive,root,rows.selection)
    ttk.Button(analysis_bar,text='Research workbench',command=research_workbench).pack(side='left',padx=3)
    query.bind('<Return>',search)
    root.bind('<Control-f>',lambda _:query.focus_set())
    rows.bind('<<TreeviewSelect>>',select)
    search()
    root.mainloop()
