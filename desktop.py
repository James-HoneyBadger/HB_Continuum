"""Plain-text local viewer; never renders HTML or opens attachments."""
def launch(archive):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    root=tk.Tk(); root.title('HB Dispatch'); root.geometry('900x600')
    query=ttk.Entry(root); query.pack(fill='x',padx=10,pady=8)
    rows=ttk.Treeview(root,columns=('subject','sender'),show='headings'); rows.heading('subject',text='Subject'); rows.heading('sender',text='Sender')
    body=tk.Text(root,wrap='word',state='disabled')
    def search(*_):
        try:
            hits=archive.find(query.get()) if query.get().strip() else archive.db.execute('SELECT hash,subject,sender FROM messages LIMIT 100').fetchall()
            rows.delete(*rows.get_children())
            for h,s,f in hits: rows.insert('', 'end',iid=h,values=(s,f))
        except Exception as e: messagebox.showerror('Search',str(e))
    def select(*_):
        if not rows.selection(): return
        data=archive.db.execute('SELECT subject,sender,date,body FROM messages WHERE hash=?',(rows.selection()[0],)).fetchone()
        body.configure(state='normal'); body.delete('1.0','end'); body.insert('1.0','\n\n'.join(data)); body.configure(state='disabled')
    def import_files():
        try:
            for f in filedialog.askopenfilenames(filetypes=[('Email','*.eml')]):
                from pathlib import Path
                archive.ingest(Path(f).read_bytes())
            search()
        except Exception as e: messagebox.showerror('Import',str(e))
    bar=ttk.Frame(root); bar.pack(fill='x'); ttk.Button(bar,text='Search',command=search).pack(side='left'); ttk.Button(bar,text='Import EML',command=import_files).pack(side='left'); query.bind('<Return>',search)
    rows.pack(fill='both',expand=True); rows.bind('<<TreeviewSelect>>',select); body.pack(fill='both',expand=True); search(); root.mainloop()
