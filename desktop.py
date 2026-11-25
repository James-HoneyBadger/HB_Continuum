"""Local correspondence workstation. Plain text only; no remote rendering."""
def launch(archive):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from pathlib import Path
    root=tk.Tk()
    root.title('HB Dispatch — Correspondence Workstation')
    root.geometry('1150x760')
    root.minsize(720,480)
    toolbar=ttk.Frame(root,padding=10)
    toolbar.pack(fill='x')
    query=ttk.Entry(toolbar)
    query.pack(side='left',fill='x',expand=True)
    status=tk.StringVar()
    pane=ttk.Panedwindow(root,orient='vertical')
    pane.pack(fill='both',expand=True,padx=10,pady=5)
    listing=ttk.Frame(pane)
    rows=ttk.Treeview(listing,columns=('subject','sender'),show='headings',selectmode='extended')
    rows.heading('subject',text='Subject')
    rows.heading('sender',text='Sender')
    rows.column('subject',width=550)
    rows.column('sender',width=260)
    scroll=ttk.Scrollbar(listing,orient='vertical',command=rows.yview)
    rows.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y')
    rows.pack(fill='both',expand=True)
    pane.add(listing,weight=2)
    reader=ttk.Frame(pane)
    body=tk.Text(reader,wrap='word',state='disabled',padx=12,pady=10)
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
            hits=archive.find(query.get().strip()) if query.get().strip() else archive.recent()
            rows.delete(*rows.get_children())
            display('')
            for h,s,f in hits: rows.insert('', 'end',iid=h,values=(s,f))
            stats=archive.stats()
            status.set(f"{len(hits)} shown (up to 100)  |  {stats['messages']} archived messages  |  {stats['origins']} mailbox origins")
        except Exception as e: messagebox.showerror('Search',str(e))
    def select(*_):
        selection=rows.selection()
        if not selection: return
        try:
            h=selection[0]
            data=archive.details(h)
            header='\n'.join(f"{k}: {data[k]}" for k in ('subject','sender','date','message_id','reply_to'))
            display(header+'\nSHA-256: '+h+'\n\n'+data['body'])
        except Exception as e: messagebox.showerror('Message',str(e))
    def import_files():
        try:
            for f in filedialog.askopenfilenames(filetypes=[('Email','*.eml')]):
                path=Path(f)
                if path.stat().st_size>64*1024*1024: raise ValueError('Message exceeds 64 MiB limit')
                archive.ingest(path.read_bytes())
            search()
        except Exception as e: messagebox.showerror('Import',str(e))
    def verify():
        try:
            bad=archive.verify()
            if bad: messagebox.showwarning('Integrity check',f'{len(bad)} messages failed verification.\n'+'\n'.join(bad[:10]))
            else: messagebox.showinfo('Integrity check','All indexed original messages match their stored hashes.')
        except Exception as e: messagebox.showerror('Integrity check',str(e))
    def export():
        selected=rows.selection()
        if not selected: return messagebox.showinfo('Export','Select one or more messages first.')
        parent=filedialog.askdirectory(title='Choose parent folder for evidence package')
        if not parent: return
        from datetime import datetime,timezone
        dest=Path(parent)/('evidence-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        try:
            archive.export(selected,dest)
            messagebox.showinfo('Export complete',str(dest))
        except Exception as e: messagebox.showerror('Export',str(e))
    for label,fn in [('Search',search),('Import EML',import_files),('Verify',verify),('Export selected',export)]:
        ttk.Button(toolbar,text=label,command=fn).pack(side='left',padx=3)
    query.bind('<Return>',search)
    root.bind('<Control-f>',lambda _:query.focus_set())
    rows.bind('<<TreeviewSelect>>',select)
    search()
    root.mainloop()
