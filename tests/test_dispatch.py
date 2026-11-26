# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import unittest,tempfile, json, sqlite3, io, contextlib
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
    def test_version_flag(self):
        out=io.StringIO()
        with mock.patch('sys.argv',['dispatch.py','--version']), contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as exit:
                main()
        self.assertEqual(exit.exception.code,0)
        self.assertEqual(out.getvalue().strip(),f'dispatch.py {__version__}')
if __name__=='__main__': unittest.main()
