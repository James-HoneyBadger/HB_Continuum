# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Background search for the Tk workstation. No widgets are touched off-thread."""
import queue, sqlite3, threading
from pathlib import Path

def open_readonly(root):
    conn = sqlite3.connect(str(Path(root) / 'archive.sqlite3'), timeout=30)
    conn.execute('PRAGMA query_only=ON')
    return conn

def find_readonly(conn, query, limit=100):
    limit = max(1, min(int(limit), 5000))
    try:
        return conn.execute('SELECT hash,subject,sender FROM search WHERE search MATCH ? LIMIT ?', (query, limit)).fetchall()
    except sqlite3.OperationalError:
        phrase = '"' + query.replace('"', '""') + '"'
        try:
            return conn.execute('SELECT hash,subject,sender FROM search WHERE search MATCH ? LIMIT ?', (phrase, limit)).fetchall()
        except sqlite3.OperationalError:
            return []

def recent_readonly(conn, limit=100):
    return conn.execute('SELECT hash,subject,sender FROM messages ORDER BY rowid DESC LIMIT ?', (max(1, min(int(limit), 5000)),)).fetchall()

def stats_readonly(conn):
    return {'messages': conn.execute('SELECT count(*) FROM messages').fetchone()[0],
            'origins': conn.execute('SELECT count(*) FROM origins').fetchone()[0]}

class SearchController:
    """Runs one daemon thread per query and marshals results back with after()."""
    def __init__(self, archive_root, query_fn, after_scheduler, after_canceller=None, interval_ms=75):
        self._root = Path(archive_root)
        self._query_fn = query_fn
        self._after = after_scheduler
        self._after_cancel = after_canceller
        self._interval_ms = interval_ms
        self._results = queue.SimpleQueue()
        self._generation = 0
        self._busy = False
        self._after_id = None
        self.on_result = None
        self.on_error = None

    @property
    def busy(self):
        return self._busy

    def submit(self, term):
        self._generation += 1
        self._busy = True
        gen = self._generation
        threading.Thread(target=self._worker, args=(gen, term), daemon=True).start()
        if self._after_id is None:
            self._after_id = self._after(self._interval_ms, self._poll)

    def _worker(self, gen, term):
        try:
            conn = open_readonly(self._root)
            try:
                hits = self._query_fn(conn, term)
                stats = stats_readonly(conn)
            finally:
                conn.close()
            if gen != self._generation:
                return
            self._results.put(('ok', gen, hits, stats))
        except Exception as exc:
            self._results.put(('err', gen, exc))

    def _poll(self):
        self._after_id = None
        try:
            while True:
                item = self._results.get_nowait()
                kind, gen = item[0], item[1]
                if gen != self._generation:
                    continue
                self._busy = False
                if kind == 'ok':
                    if self.on_result:
                        self.on_result(item[2], item[3])
                elif self.on_error:
                    self.on_error(item[2])
                return
        except queue.Empty:
            pass
        if self._busy:
            self._after_id = self._after(self._interval_ms, self._poll)

    def cancel(self):
        self._generation += 1
        self._busy = False

    def destroy(self):
        self.cancel()
        if self._after_id is not None and self._after_cancel is not None:
            self._after_cancel(self._after_id)
            self._after_id = None
