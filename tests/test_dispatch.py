# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import unittest,tempfile, json, sqlite3, io, contextlib, imaplib
from unittest import mock
from pathlib import Path
from dispatch import Archive, __version__, main
RAW=b'From: sender@example.invalid\r\nSubject: Synthetic invoice\r\nMessage-ID: <test@example.invalid>\r\n\r\nTest evidence only.\r\n'
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.a=Archive(Path(self.tmp.name)/'archive')
    def tearDown(self): self.a.db.close(); self.tmp.cleanup()
    def test_roundtrip(self):
        h=self.a.ingest(RAW,('test','INBOX','1','2')); self.assertEqual(h,self.a.ingest(RAW)); self.assertEqual(len(self.a.find('invoice')),1); self.assertEqual(self.a.verify(),[])
        dest=Path(self.tmp.name)/'export'; self.a.export([h],dest); self.assertEqual((dest/(h+'.eml')).read_bytes(),RAW); self.assertEqual(json.loads((dest/'manifest.json').read_text())[0]['origins'][0],['test','INBOX','1','2'])
    def test_tamper(self):
        h=self.a.ingest(RAW); (self.a.raw/(h+'.eml')).write_bytes(b'changed'); self.assertEqual(self.a.verify(),[h]); self.assertRaises(ValueError,self.a.ingest,RAW)
    def test_origin_conflict(self):
        origin=('test','INBOX','1','2'); self.a.ingest(RAW,origin); self.assertRaises(ValueError,self.a.ingest,RAW+b'changed',origin); self.assertEqual(len(self.a.find('invoice')),1)
    def test_search_bound(self):
        self.a.ingest(RAW); self.assertEqual(self.a.find('nonexistent'),[]); self.assertEqual(len(self.a.find('evidence')),1)
    def test_hostile_charset(self):
        self.a.ingest(b'Content-Type: text/plain; charset=x-does-not-exist\r\n\r\ncaf\xe9 bill\r\n'); self.assertEqual(len(self.a.find('bill')),1); self.assertEqual(self.a.verify(),[])
    def test_fts_garbage(self):
        self.a.ingest(RAW)
        for q in ('a:b','-invoice','"unterminated','OR','*'): self.assertIsInstance(self.a.find(q),list)
        self.assertEqual(len(self.a.find('invoice NOT nonexistent')),1); self.assertEqual(len(self.a.find('invo*')),1)
    def test_sync_missing_uidvalidity(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[None])
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertRaises(RuntimeError,self.a.sync,'host','user','pw')
    def test_foreign_keys_enforced(self):
        self.assertRaises(sqlite3.IntegrityError,self.a.db.execute,'INSERT INTO origins VALUES(?,?,?,?,?)',('a','f','1','2','0'*64))
    def test_failed_export_cleanup(self):
        h=self.a.ingest(RAW)
        dest=Path(self.tmp.name)/'failed-export'
        (self.a.raw/(h+'.eml')).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.a.export([h],dest)
        self.assertFalse(dest.exists())
    def test_unknown_export_does_not_create_destination(self):
        dest=Path(self.tmp.name)/'unknown-export'
        with self.assertRaises(ValueError):
            self.a.export(['0'*64],dest)
        self.assertFalse(dest.exists())
    def test_workspace_queries(self):
        h=self.a.ingest(RAW,('test','INBOX','1','2'))
        self.assertEqual(self.a.stats(),{'messages':1,'origins':1})
        self.assertEqual(self.a.recent()[0][0],h)
        self.assertEqual(self.a.details(h)['subject'],'Synthetic invoice')
    def test_existing_export_is_not_modified(self):
        h=self.a.ingest(RAW)
        dest=Path(self.tmp.name)/'existing'
        dest.mkdir()
        sentinel=dest/'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            self.a.export([h],dest)
        self.assertEqual(sentinel.read_text(),'keep')
    def test_thread_reconstruction(self):
        parent=self.a.ingest(RAW)
        reply=self.a.ingest(b'From: other@example.invalid\r\nMessage-ID: <reply@example.invalid>\r\nIn-Reply-To: <test@example.invalid>\r\n\r\nReply.\r\n')
        unrelated=self.a.ingest(b'Subject: Synthetic invoice\r\n\r\nUnrelated.\r\n')
        for h in (parent,reply):
            self.assertEqual({m['sha256'] for m in self.a.thread(h)},{parent,reply})
        self.assertEqual(len(self.a.thread(unrelated)),1)
        self.assertEqual(dict(self.a.correspondents())['other@example.invalid'],1)
    def test_html_only_body_is_searchable(self):
        raw=(b'From: a@example.invalid\r\nSubject: Newsletter\r\nMessage-ID: <html@example.invalid>\r\n'
             b'MIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'
             b'<html><head><style>b{color:red}</style></head><body>'
             b'<p>Quarterly&nbsp;<b>revenue</b> report</p><script>track()</script></body></html>\r\n')
        h=self.a.ingest(raw)
        body=self.a.details(h)['body']
        self.assertIn('revenue',body)
        self.assertNotIn('track',body); self.assertNotIn('color:red',body)
        self.assertEqual(len(self.a.find('revenue')),1)
    def test_plain_text_preferred_over_html_alternative(self):
        raw=(b'Message-ID: <alt@example.invalid>\r\nMIME-Version: 1.0\r\n'
             b'Content-Type: multipart/alternative; boundary="B"\r\n\r\n'
             b'--B\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nplain ledger\r\n'
             b'--B\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>html ledger</p>\r\n--B--\r\n')
        body=self.a.details(self.a.ingest(raw))['body']
        self.assertIn('plain ledger',body); self.assertNotIn('html ledger',body)
    def test_html_attachment_ignored(self):
        raw=(b'Message-ID: <attach@example.invalid>\r\nMIME-Version: 1.0\r\n'
             b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
             b'--B\r\nContent-Type: text/plain\r\n\r\nvisible note\r\n'
             b'--B\r\nContent-Type: text/html\r\nContent-Disposition: attachment; filename="page.html"\r\n\r\n'
             b'<p>hidden attachment</p>\r\n--B--\r\n')
        body=self.a.details(self.a.ingest(raw))['body']
        self.assertIn('visible note',body); self.assertNotIn('hidden attachment',body)
    def test_malformed_html_does_not_raise(self):
        raw=(b'Message-ID: <broken@example.invalid>\r\nContent-Type: text/html\r\n\r\n'
             b'<p>unclosed <b>markup &amp; entities &bogus; <table><tr><td>cell\r\n')
        body=self.a.details(self.a.ingest(raw))['body']
        self.assertIn('unclosed',body); self.assertIn('cell',body)
    def test_reindex_repairs_legacy_html_only_message(self):
        raw=(b'Subject: Legacy letter\r\nMessage-ID: <legacy@example.invalid>\r\n'
             b'Content-Type: text/html; charset=utf-8\r\n\r\n<p>archived annex</p>\r\n')
        h=self.a.ingest(raw)
        with self.a.db:
            self.a.db.execute('UPDATE messages SET body=? WHERE hash=?',('',h))
            self.a.db.execute('DELETE FROM search WHERE hash=?',(h,))
        self.assertEqual(self.a.find('annex'),[])
        self.assertEqual(self.a.reindex(),1)
        self.assertIn('archived annex',self.a.details(h)['body'])
        self.assertEqual(len(self.a.find('annex')),1)
        self.assertEqual(self.a.reindex(),1)
        self.assertEqual(len(self.a.find('annex')),1)
    def test_reindex_refuses_tampered_raw(self):
        h=self.a.ingest(RAW)
        (self.a.raw/(h+'.eml')).write_bytes(b'changed')
        self.assertRaises(ValueError,self.a.reindex)
    def test_sync_retries_transient_abort(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'9'])
        m.uid.side_effect=[('OK',[b'7']), imaplib.IMAP4.abort('connection reset'), ('OK',[(b'7',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m), mock.patch('dispatch.time.sleep'):
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(self.a.failures(),[])
        self.assertEqual(len(self.a.find('invoice')),1)
    def test_sync_quarantines_repeatedly_failing_message(self):
        good=b'Subject: Second letter\r\nMessage-ID: <2@example.invalid>\r\n\r\nsecond body\r\n'
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'42'])
        bad_fetch=('OK',[(b'1',b'x'),(b'2',b'y')])
        search=('OK',[b'1 2'])
        m.uid.side_effect=[search,bad_fetch,search,bad_fetch,search,bad_fetch,
                           search,('OK',[(b'2',good)]),search]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            for attempt in (1,2,3):
                self.assertRaises(RuntimeError,self.a.sync,'host','user','pw')
                (row,)=self.a.failures()
                self.assertEqual(row[4],attempt)
            self.assertEqual(self.a.sync('host','user','pw'),1)
            self.assertEqual(self.a.sync('host','user','pw'),0)
        self.assertEqual([r[3] for r in self.a.failures()],['1'])
        self.assertEqual(len(self.a.find('second')),1)
        self.assertEqual(self.a.stats(),{'messages':1,'origins':1})
    def test_successful_sync_clears_recorded_failure(self):
        self.a._record_failure(('host|user','INBOX','9','5'),'RuntimeError: boom')
        self.assertEqual(len(self.a.failures()),1)
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'9'])
        m.uid.side_effect=[('OK',[b'5']),('OK',[(b'5',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(self.a.failures(),[])
    def test_version_flag(self):
        out=io.StringIO()
        with mock.patch('sys.argv',['dispatch.py','--version']), contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as exit:
                main()
        self.assertEqual(exit.exception.code,0)
        self.assertEqual(out.getvalue().strip(),f'dispatch.py {__version__}')
if __name__=='__main__': unittest.main()
