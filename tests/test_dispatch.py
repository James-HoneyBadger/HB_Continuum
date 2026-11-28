# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import unittest,tempfile, json, sqlite3, io, contextlib, imaplib
from unittest import mock
from pathlib import Path
from dispatch import Archive, SyncInterrupted, __version__, main, parse_folder_list, read_mbox
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
        self.assertRaises(sqlite3.IntegrityError,self.a.db.execute,
                          'INSERT INTO origins(account,folder,validity,uid,hash) VALUES(?,?,?,?,?)',('a','f','1','2','0'*64))
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
        self.assertEqual(self.a.stats(),{'messages':1,'origins':1,'attachments':0})
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
    def test_named_text_part_stays_out_of_body(self):
        raw=(b'Message-ID: <named@example.invalid>\r\nMIME-Version: 1.0\r\n'
             b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
             b'--B\r\nContent-Type: text/plain\r\n\r\nreal body\r\n'
             b'--B\r\nContent-Type: text/plain; name="notes.txt"\r\n'
             b'Content-Disposition: inline; filename="notes.txt"\r\n\r\nattached notes\r\n--B--\r\n')
        body=self.a.details(self.a.ingest(raw))['body']
        self.assertIn('real body',body); self.assertNotIn('attached notes',body)
        self.assertEqual(self.a.attachments(self.a.recent()[0][0])[0][0],'notes.txt')
    def test_attachment_only_message_still_indexes_text(self):
        raw=(b'Message-ID: <only@example.invalid>\r\nMIME-Version: 1.0\r\n'
             b'Content-Type: text/plain; name="dump.txt"\r\n'
             b'Content-Disposition: attachment; filename="dump.txt"\r\n\r\nsalvaged text\r\n')
        body=self.a.details(self.a.ingest(raw))['body']
        self.assertIn('salvaged text',body)
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
    def test_connection_aborts_do_not_quarantine_a_healthy_message(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'21'])
        interrupted=[('OK',[b'4'])]+[imaplib.IMAP4.abort('connection reset')]*3
        m.uid.side_effect=interrupted*3+[('OK',[b'4']),('OK',[(b'4',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m), mock.patch('dispatch.time.sleep'):
            for _ in range(3):
                self.assertRaises(SyncInterrupted,self.a.sync,'host','user','pw')
            self.assertEqual(self.a.failures(),[])
            self.assertEqual(self.a._sync_state('host|user','INBOX','21'),0)
            self.assertIn('SyncInterrupted',self.a.sync_log()[0][5])
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(len(self.a.find('invoice')),1)
        self.assertEqual(self.a.failures(),[])
        self.assertEqual(self.a._sync_state('host|user','INBOX','21'),4)
    def test_empty_fetch_is_recorded_as_a_message_failure(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'22'])
        m.uid.side_effect=[('OK',[b'9']),('OK',[(b'9',b'')])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertRaises(RuntimeError,self.a.sync,'host','user','pw')
        (row,)=self.a.failures()
        self.assertEqual((row[3],row[4]),('9',1))
        self.assertIn('Empty fetch response',row[5])
        self.assertEqual(self.a.stats()['messages'],0)
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
        self.assertEqual(self.a.stats(),{'messages':1,'origins':1,'attachments':0})
    def test_successful_sync_clears_recorded_failure(self):
        self.a._record_failure(('host|user','INBOX','9','5'),'RuntimeError: boom')
        self.assertEqual(len(self.a.failures()),1)
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'9'])
        m.uid.side_effect=[('OK',[b'5']),('OK',[(b'5',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(self.a.failures(),[])
    def test_attachments_are_archived_and_deduplicated(self):
        blob=b'\x89PNG\r\n\x1a\n not really a png, but bytes '
        def message(mid):
            return (b'Message-ID: <'+mid+b'>\r\nMIME-Version: 1.0\r\n'
                    b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
                    b'--B\r\nContent-Type: text/plain\r\n\r\nsee attached\r\n'
                    b'--B\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename="report.bin"\r\n'
                    b'Content-Transfer-Encoding: base64\r\n\r\n'+__import__('base64').b64encode(blob)+b'\r\n--B--\r\n')
        first=self.a.ingest(message(b'one@example.invalid'))
        second=self.a.ingest(message(b'two@example.invalid'))
        (row,)=self.a.attachments(first)
        self.assertEqual(row[0],'report.bin'); self.assertEqual(row[1],'application/octet-stream')
        self.assertEqual(row[2],len(blob)); self.assertEqual(self.a.attachment_bytes(row[3]),blob)
        self.assertEqual(self.a.attachments(second)[0][3],row[3])
        stored=list((self.a.root/'attachments').rglob('*'))
        self.assertEqual(len([p for p in stored if p.is_file()]),1)
        self.assertEqual(self.a.stats()['attachments'],2)
        self.assertEqual(self.a.verify_attachments(),[])
    def test_reindex_recovers_attachments_for_legacy_archive(self):
        body=b'Subject: Legacy\r\nMessage-ID: <legacy-attach@example.invalid>\r\nMIME-Version: 1.0\r\n'
        raw=(body+b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
             b'--B\r\nContent-Type: text/plain\r\n\r\ntext\r\n'
             b'--B\r\nContent-Type: text/csv\r\nContent-Disposition: attachment; filename="rows.csv"\r\n\r\n'
             b'a,b\r\n1,2\r\n--B--\r\n')
        h=self.a.ingest(raw)
        with self.a.db: self.a.db.execute('DELETE FROM attachments WHERE message=?',(h,))
        self.assertEqual(self.a.attachments(h),[])
        self.assertEqual(self.a.reindex(),1)
        (row,)=self.a.attachments(h)
        self.assertEqual(row[0],'rows.csv'); self.assertEqual(self.a.attachment_bytes(row[3]),b'a,b\r\n1,2')
    def test_attachment_integrity_is_checked(self):
        raw=(b'MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary="B"\r\n\r\n'
             b'--B\r\nContent-Type: text/plain\r\n\r\ntext\r\n'
             b'--B\r\nContent-Type: text/plain\r\nContent-Disposition: attachment; filename="n.txt"\r\n\r\nnote\r\n--B--\r\n')
        (_,_,_,sha256),=self.a.attachments(self.a.ingest(raw))
        (self.a.root/'attachments'/sha256[:2]/sha256).write_bytes(b'tampered')
        self.assertEqual(self.a.verify_attachments(),[sha256])
        self.assertRaises(ValueError,self.a.attachment_bytes,sha256)
        self.assertRaises(ValueError,self.a.attachment_bytes,'../escape')
    def test_incremental_sync_uses_uid_watermark(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'7'])
        m.uid.side_effect=[('OK',[b'5']),('OK',[(b'5',RAW)]),('OK',[b''])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual(self.a.sync('host','user','pw'),1)
            self.assertEqual(self.a.sync('host','user','pw'),0)
        self.assertEqual(m.uid.call_args_list[0].args,('search',None,'ALL'))
        self.assertEqual(m.uid.call_args_list[2].args,('search',None,'6:*'))
        self.assertEqual(self.a._sync_state('host|user','INBOX','7'),5)
    def test_batch_limit_resumes_from_watermark(self):
        from preferences import save
        save(self.a.root,{'batch_limit':1})
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'3'])
        first=b'Subject: One\r\n\r\none\r\n'; second=b'Subject: Two\r\n\r\ntwo\r\n'
        m.uid.side_effect=[('OK',[b'1 2 3']),('OK',[(b'1',first)]),
                           ('OK',[b'2 3']),('OK',[(b'2',second)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual(self.a.sync('host','user','pw'),1)
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(m.uid.call_args_list[2].args,('search',None,'2:*'))
        self.assertEqual(self.a._sync_state('host|user','INBOX','3'),2)
        self.assertEqual(len(self.a.find('two')),1)
    def test_changed_uidvalidity_rescans_mailbox(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1'])
        m.response.side_effect=[('UIDVALIDITY',[b'7']),('UIDVALIDITY',[b'8'])]
        m.uid.side_effect=[('OK',[b'5']),('OK',[(b'5',RAW)]),('OK',[b'5']),('OK',[(b'5',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual(self.a.sync('host','user','pw'),1)
            self.assertEqual(self.a.sync('host','user','pw'),1)
        self.assertEqual(m.uid.call_args_list[2].args,('search',None,'ALL'))
        self.assertEqual(self.a.stats()['origins'],2)
    def test_search_filters_by_sender_and_date(self):
        def message(mid,sender,date):
            return (f'From: {sender}\r\nDate: {date}\r\nMessage-ID: <{mid}>\r\nSubject: Statement\r\n\r\nledger note\r\n').encode()
        self.a.ingest(message('a@example.invalid','Alice <alice@example.invalid>','Mon, 1 Jan 2024 12:00:00 +0000'))
        self.a.ingest(message('b@example.invalid','bob@example.invalid','Tue, 2 Jan 2024 23:30:00 -0800'))
        self.a.ingest(message('c@example.invalid','CAROL@example.invalid','not a date'))
        self.assertEqual(len(self.a.find('ledger')),3)
        self.assertEqual([r[2] for r in self.a.find('ledger',sender='alice')],['Alice <alice@example.invalid>'])
        self.assertEqual([r[2] for r in self.a.find('ledger',after='2024-01-02')],['bob@example.invalid'])
        self.assertEqual([r[2] for r in self.a.find('ledger',before='2024-01-01')],['Alice <alice@example.invalid>'])
        self.assertEqual([r[2] for r in self.a.find('ledger',after='2024-01-01',before='2024-01-01')],['Alice <alice@example.invalid>'])
        self.assertEqual(self.a.find('ledger',sender='alice',after='2024-01-02'),[])
        self.assertEqual(self.a.find('ledger',sender='%'),[])
        self.assertRaises(ValueError,self.a.find,'ledger',100,None,'not-a-date')
        self.assertEqual([r[2] for r in self.a.find('',sender='alice')],['Alice <alice@example.invalid>'])
        self.assertEqual([r[2] for r in self.a.find('',after='2024-01-02')],['bob@example.invalid'])
        self.assertEqual(self.a.find('',after='2025-01-01'),[])
    def test_reindex_backfills_dates_for_legacy_archive(self):
        dated=self.a.ingest(b'Date: Mon, 1 Jan 2024 12:00:00 +0000\r\nMessage-ID: <d@example.invalid>\r\n\r\ndated\r\n')
        undated=self.a.ingest(RAW)
        with self.a.db:
            self.a.db.execute('UPDATE messages SET sent_ts=NULL')
            self.a.db.execute('DELETE FROM search')
        self.assertEqual(self.a.reindex(),2)
        stamp=lambda h: self.a.db.execute('SELECT sent_ts FROM messages WHERE hash=?',(h,)).fetchone()[0]
        self.assertEqual(stamp(dated),1704110400)
        self.assertIsNone(stamp(undated))
        self.assertEqual(len(self.a.find('dated')),1)
    def test_reindex_adopts_orphaned_raw_file(self):
        import hashlib as hashlib_module
        raw=b'Subject: Orphaned\r\nMessage-ID: <orphan@example.invalid>\r\n\r\norphaned body\r\n'
        digest=hashlib_module.sha256(raw).hexdigest()
        (self.a.raw/(digest+'.eml')).write_bytes(raw)
        self.assertEqual(self.a.find('orphaned'),[])
        self.assertEqual(self.a.reindex(),1)
        self.assertEqual(len(self.a.find('orphaned')),1)
        self.assertEqual(self.a.verify(),[])
        self.assertEqual(self.a.reindex(),1)
    def test_reindex_ignores_misnamed_raw_file(self):
        (self.a.raw/('0'*64+'.eml')).write_bytes(b'Subject: Fake\r\n\r\nnot matching its name\r\n')
        self.assertEqual(self.a.reindex(),0)
        self.assertEqual(self.a.find('fake'),[])
    def test_mbox_import_preserves_messages_and_quoting(self):
        mbox=(b'From alice@example.invalid Mon Jan  1 00:00:00 2024\n'
              b'Subject: First archived\nMessage-ID: <mbox1@example.invalid>\n\n'
              b'line one\n>From the archive\n\n'
              b'From bob@example.invalid Tue Jan  2 00:00:00 2024\n'
              b'Subject: Second archived\nMessage-ID: <mbox2@example.invalid>\n\n'
              b'line two\n')
        path=Path(self.tmp.name)/'mail.mbox'; path.write_bytes(mbox)
        self.assertEqual(self.a.import_mbox(path),(2,0))
        self.assertEqual(len(self.a.find('archived')),2)
        first=self.a.find('"line one"')[0][0]
        self.assertIn('From the archive',self.a.details(first)['body'])
        self.assertEqual(self.a.import_mbox(path),(2,0))
        self.assertEqual(self.a.stats()['messages'],2)
        self.assertEqual(self.a.verify(),[])
    def test_mbox_import_skips_unarchivable_message(self):
        mbox=(b'From a@example.invalid Mon Jan  1 00:00:00 2024\nSubject: Good one\n\nbody\n'
              b'From b@example.invalid Tue Jan  2 00:00:00 2024\nSubject: Bad one\n\nbody\n')
        path=Path(self.tmp.name)/'partial.mbox'; path.write_bytes(mbox)
        real=self.a.ingest
        def failing(raw,origin=None):
            if b'Bad one' in raw: raise ValueError('Message exceeds 64 MiB limit')
            return real(raw,origin)
        self.a.ingest=failing
        self.assertEqual(self.a.import_mbox(path),(1,1))
        self.assertEqual(len(self.a.find('Good')),1)
    def test_read_mbox_handles_edges(self):
        self.assertEqual(list(read_mbox(io.BytesIO(b''))),[])
        self.assertEqual(list(read_mbox(io.BytesIO(b'junk without separator'))),[])
        self.assertEqual(list(read_mbox(io.BytesIO(b'From a@b Mon Jan  1 00:00:00 2024\nSubject: x\n\nno trailing newline'))),
                         [b'Subject: x\n\nno trailing newline'])
    def test_directory_import_covers_maildir_trees(self):
        tree=Path(self.tmp.name)/'Maildir'
        for name,body in (('cur/1.eml',b'Subject: Cur one\r\n\r\nfirst\r\n'),
                          ('new/2.eml',b'Subject: New two\r\n\r\nsecond\r\n')):
            (tree/name).parent.mkdir(parents=True,exist_ok=True); (tree/name).write_bytes(body)
        (tree/'.hidden').mkdir(); (tree/'.hidden/3.eml').write_bytes(b'Subject: Hidden\r\n\r\nhidden\r\n')
        self.assertEqual(self.a.import_directory(tree),(2,0))
        self.assertEqual(len(self.a.find('Cur')),1); self.assertEqual(len(self.a.find('New')),1)
        self.assertEqual(self.a.find('Hidden'),[])
        self.assertEqual(self.a.import_directory(tree),(2,0))
        self.assertEqual(self.a.stats()['messages'],2)
    def test_sync_log_records_success_and_failure_without_secrets(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'11'])
        m.uid.side_effect=[('OK',[b'3']),('OK',[(b'3',RAW)])]
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.a.sync('host','user','hunter2-secret')
        (row,)=self.a.sync_log()
        self.assertEqual((row[0],row[1],row[4]),('host|user','INBOX',1))
        self.assertIsNone(row[5])
        broken=mock.MagicMock(); broken.__enter__.return_value=broken
        broken.select.return_value=('OK',[b'1']); broken.response.return_value=('UIDVALIDITY',[None])
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=broken):
            self.assertRaises(RuntimeError,self.a.sync,'host','user','hunter2-secret')
        log=self.a.sync_log()
        self.assertEqual(len(log),2)
        self.assertEqual(log[0][4],0); self.assertIn('Missing UIDVALIDITY',log[0][5])
        self.assertNotIn('hunter2-secret',json.dumps(log))
    def test_sync_log_is_bounded(self):
        with mock.patch('dispatch.SYNC_LOG_LIMIT',2):
            for _ in range(5): self.a._log_sync('h|u','INBOX','2024-01-01 00:00:00',0,None)
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM sync_log').fetchone()[0],2)
    def test_recipients_are_preserved_and_searchable(self):
        raw=(b'From: Alice <alice@example.invalid>\r\nTo: Bob <bob@example.invalid>, carol@example.invalid\r\n'
             b'Cc: Dave <dave@example.invalid>\r\nBcc: hidden@example.invalid\r\n'
             b'Subject: Quarterly\r\nMessage-ID: <q@example.invalid>\r\n\r\nbody text\r\n')
        h=self.a.ingest(raw)
        data=self.a.details(h)
        self.assertEqual(data['recipient'],'Bob <bob@example.invalid>, carol@example.invalid')
        self.assertEqual(data['cc'],'Dave <dave@example.invalid>')
        self.assertEqual(data['bcc'],'hidden@example.invalid')
        self.assertEqual(len(self.a.find('recipient:carol')),1)
        self.assertEqual(len(self.a.find('cc:dave')),1)
        self.assertEqual(len(self.a.find('bcc:hidden')),1)
        self.assertEqual(len(self.a.find('carol')),1)
        self.assertEqual([r[0] for r in self.a.find('',recipient='hidden')],[h])
        self.assertEqual([r[0] for r in self.a.find('',recipient='dave')],[h])
        self.assertEqual(self.a.find('',recipient='nobody'),[])
    def test_legacy_archive_gains_recipient_index(self):
        root=Path(self.tmp.name)/'legacy'; raw=root/'raw'; raw.mkdir(parents=True)
        message=(b'From: old@example.invalid\r\nTo: keeper@example.invalid\r\nSubject: Legacy letter\r\n'
                 b'Message-ID: <legacy-headers@example.invalid>\r\n\r\nlegacy body\r\n')
        digest=__import__('hashlib').sha256(message).hexdigest()
        (raw/(digest+'.eml')).write_bytes(message)
        legacy=sqlite3.connect(root/'archive.sqlite3')
        legacy.executescript("""CREATE TABLE messages(hash TEXT PRIMARY KEY, subject TEXT, sender TEXT, date TEXT,
            message_id TEXT, reply_to TEXT, body TEXT);
            CREATE VIRTUAL TABLE search USING fts5(hash UNINDEXED, subject, sender, body);
            CREATE TABLE origins(account TEXT, folder TEXT, validity TEXT, uid TEXT, hash TEXT NOT NULL REFERENCES messages(hash), PRIMARY KEY(account,folder,validity,uid));""")
        legacy.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(digest,'Legacy letter','old@example.invalid','','<legacy-headers@example.invalid>','','legacy body'))
        legacy.execute('INSERT INTO search VALUES(?,?,?,?)',(digest,'Legacy letter','old@example.invalid','legacy body'))
        legacy.commit(); legacy.close()
        archive=Archive(root)
        try:
            self.assertEqual(len(archive.find('legacy body')),1)
            self.assertEqual([r[0] for r in archive.find('',recipient='keeper')],[digest])
            self.assertEqual(archive.details(digest)['recipient'],'keeper@example.invalid')
            self.assertEqual(archive.db.execute("SELECT value FROM meta WHERE key='headers_backfill'").fetchone()[0],'done')
            self.assertEqual(archive.verify(),[])
        finally: archive.db.close()
    def test_header_backfill_resumes_from_its_checkpoint(self):
        first=self.a.ingest(b'To: one@example.invalid\r\nSubject: One\r\nMessage-ID: <1@example.invalid>\r\n\r\none\r\n')
        second=self.a.ingest(b'To: two@example.invalid\r\nSubject: Two\r\nMessage-ID: <2@example.invalid>\r\n\r\ntwo\r\n')
        with self.a.db:
            self.a.db.execute('UPDATE messages SET recipient=NULL')
            self.a.db.execute('UPDATE search SET recipient=?',('',))
        rowid=self.a.db.execute('SELECT rowid FROM messages WHERE hash=?',(first,)).fetchone()[0]
        with self.a.db:
            self.a.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('headers_backfill',?)",(str(rowid),))
        self.a._backfill_headers()
        self.assertIsNone(self.a.details(first)['recipient'])
        self.assertEqual(self.a.details(second)['recipient'],'two@example.invalid')
        self.assertEqual(self.a.db.execute("SELECT value FROM meta WHERE key='headers_backfill'").fetchone()[0],'done')
        with self.a.db: self.a.db.execute("DELETE FROM meta WHERE key='headers_backfill'")
        self.a._backfill_headers()
        self.assertEqual(self.a.details(first)['recipient'],'one@example.invalid')
        self.assertEqual([r[0] for r in self.a.find('',recipient='one')],[first])
    def test_reindex_populates_recipients_for_legacy_rows(self):
        h=self.a.ingest(b'To: revive@example.invalid\r\nSubject: Revive\r\nMessage-ID: <r@example.invalid>\r\n\r\nrevive body\r\n')
        with self.a.db:
            self.a.db.execute('UPDATE messages SET recipient=?,cc=?,bcc=?',('','',''))
            self.a.db.execute('DELETE FROM search')
        self.assertEqual(self.a.reindex(),1)
        self.assertEqual([r[0] for r in self.a.find('',recipient='revive')],[h])
        self.assertEqual(self.a.db.execute("SELECT value FROM meta WHERE key='headers_backfill'").fetchone()[0],'done')
    def test_mbox_export_round_trips_exactly(self):
        first=b'From: alice@example.invalid\r\nDate: Mon, 1 Jan 2024 12:00:00 +0000\r\nSubject: One\r\nMessage-ID: <1@example.invalid>\r\n\r\nFrom the archive\r\n>From quoted\r\n'
        second=b'To: bob@example.invalid\r\nSubject: Two\r\nMessage-ID: <2@example.invalid>\r\n\r\ntwo\r\n'
        a=self.a.ingest(first); b=self.a.ingest(second)
        target=Path(self.tmp.name)/'exported.mbox'
        self.a.export_mbox([a,b],target)
        self.assertTrue(target.read_text().startswith('From alice@example.invalid Mon Jan  1 12:00:00 2024\n'))
        restored=Archive(Path(self.tmp.name)/'restored')
        try:
            self.assertEqual(restored.import_mbox(target),(2,0))
            self.assertEqual(sorted(p.stem for p in restored.raw.glob('*.eml')),sorted([a,b]))
            self.assertEqual((restored.raw/(a+'.eml')).read_bytes(),first)
            self.assertEqual((restored.raw/(b+'.eml')).read_bytes(),second)
        finally: restored.db.close()
    def test_mbox_export_refuses_to_overwrite(self):
        h=self.a.ingest(RAW)
        target=Path(self.tmp.name)/'existing.mbox'; target.write_text('keep')
        self.assertRaises(FileExistsError,self.a.export_mbox,[h],target)
        self.assertEqual(target.read_text(),'keep')
        self.assertRaises(ValueError,self.a.export_mbox,['0'*64],Path(self.tmp.name)/'other.mbox')
    def test_folder_list_parsing_covers_quoted_and_nil_names(self):
        self.assertEqual(parse_folder_list(b'(\\HasNoChildren) "/" "INBOX"'),
                         {'name':'INBOX','delimiter':'/','flags':['\\HasNoChildren']})
        self.assertEqual(parse_folder_list(b'(\\HasChildren \\Noselect) "/" "[Gmail]"')['flags'],
                         ['\\HasChildren','\\Noselect'])
        self.assertEqual(parse_folder_list(b'(\\HasNoChildren) NIL "Sent Items"'),
                         {'name':'Sent Items','delimiter':'','flags':['\\HasNoChildren']})
        self.assertEqual(parse_folder_list(b'(\\HasNoChildren) "/" "A \\"quoted\\" name"')['name'],'A "quoted" name')
        self.assertIsNone(parse_folder_list(b'garbage'))
        self.assertIsNone(parse_folder_list(None))
    def test_folders_lists_mailboxes_without_selecting(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.list.return_value=('OK',[b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Archive/2024"'])
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertEqual([f['name'] for f in self.a.folders('imap.gmail.com','user','abcd efgh')],
                             ['INBOX','Archive/2024'])
        m.login.assert_called_once_with('user','abcdefgh')
        m.select.assert_not_called()
        m.uid.assert_not_called()
    def test_folders_reports_listing_failure(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.list.return_value=('NO',[None])
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
            self.assertRaises(RuntimeError,self.a.folders,'host','user','pw')
    def test_sync_accepts_several_folders_from_the_command_line(self):
        m=mock.MagicMock(); m.__enter__.return_value=m
        m.select.return_value=('OK',[b'1']); m.response.return_value=('UIDVALIDITY',[b'5'])
        m.uid.side_effect=[('OK',[b'1']),('OK',[(b'1',RAW)]),('OK',[b'9']),('OK',[(b'9',RAW)])]
        out=io.StringIO()
        with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m), mock.patch('getpass.getpass',return_value='pw'), \
             mock.patch('sys.argv',['dispatch.py','--archive',str(self.a.root),'sync','host','user','--folder','INBOX','--folder','Archive']), \
             contextlib.redirect_stdout(out):
            self.assertEqual(main(),0)
        self.assertEqual(out.getvalue().strip(),'2')
        self.assertEqual([call.args[0] for call in m.select.call_args_list],['"INBOX"','"Archive"'])
        self.assertEqual(self.a.stats()['origins'],2)
    def test_timeline_uses_stored_timestamps_and_bounds_the_result(self):
        late=self.a.ingest(b'From: b@example.invalid\r\nDate: Wed, 3 Jan 2024 00:00:00 +0000\r\nSubject: late\r\n\r\nx\r\n')
        early=self.a.ingest(b'From: a@example.invalid\r\nDate: Mon, 1 Jan 2024 00:00:00 +0000\r\nSubject: early\r\n\r\nx\r\n')
        undated=self.a.ingest(b'From: a@example.invalid\r\nSubject: undated\r\n\r\nx\r\n')
        broken=self.a.ingest(b'From: a@example.invalid\r\nDate: not a date\r\nSubject: broken\r\n\r\nx\r\n')
        undated_order=[label for _,label in sorted([(undated,'undated'),(broken,'broken')])]
        self.assertEqual([r[1] for r in self.a.timeline()],['early','late']+undated_order)
        self.assertEqual([r[0] for r in self.a.timeline(limit=2)],[early,late])
        self.assertEqual([r[1] for r in self.a.timeline(sender='b@example.invalid')],['late'])
        self.assertEqual([r[1] for r in self.a.timeline(sender='a@example.invalid',limit=1)],['early'])
        self.assertEqual(self.a.timeline(limit=0)[0][0],early)
    def test_timeline_tie_breaks_by_hash_and_skips_unordered_rows(self):
        undated=[self.a.ingest(b'Subject: first\r\nMessage-ID: <u1@example.invalid>\r\n\r\nx\r\n'),
                 self.a.ingest(b'Subject: second\r\nMessage-ID: <u2@example.invalid>\r\n\r\nx\r\n')]
        self.assertEqual([r[0] for r in self.a.timeline()],sorted(undated))
    def attachment_message(self, mid, filename, content_type):
        import base64 as b64
        return (b'Message-ID: <'+mid+b'>\r\nSubject: Filed\r\nMIME-Version: 1.0\r\n'
                b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
                b'--B\r\nContent-Type: text/plain\r\n\r\nnote body\r\n'
                b'--B\r\nContent-Type: '+content_type+b'\r\nContent-Disposition: attachment; filename="'+filename+b'"\r\n'
                b'Content-Transfer-Encoding: base64\r\n\r\n'+b64.b64encode(b'payload')+b'\r\n--B--\r\n')
    def test_search_filters_by_attachment_name_and_type(self):
        pdf=self.a.ingest(self.attachment_message(b'pdf@example.invalid',b'Invoice-2024.pdf',b'application/pdf'))
        image=self.a.ingest(self.attachment_message(b'img@example.invalid',b'photo.jpg',b'image/jpeg'))
        text=self.a.ingest(b'Subject: Filed\r\n\r\nno attachment here\r\n')
        self.assertEqual([r[0] for r in self.a.find('',attachment='invoice')],[pdf])
        self.assertEqual([r[0] for r in self.a.find('',attachment='IMAGE/')],[image])
        self.assertEqual([r[0] for r in self.a.find('',attachment='.pdf')],[pdf])
        self.assertEqual(self.a.find('',attachment='unattached'),[])
        self.assertEqual([r[0] for r in self.a.find('note',attachment='pdf')],[pdf])
        self.assertEqual(self.a.find('nothing',attachment='pdf'),[])
        self.assertEqual(self.a.find('',attachment='%'),[])
        self.assertNotIn(text,[r[0] for r in self.a.find('',attachment='photo')])
    def test_provenance_records_acquisition_time_and_duplicates(self):
        h=self.a.ingest(RAW,('imap.one|user','INBOX','1','7'))
        self.a.ingest(RAW,('imap.two|user','Archive','5','9'))
        self.a.ingest(RAW+b'other\r\n',('imap.one|user','INBOX','1','8'))
        places=self.a.provenance(h)
        self.assertEqual([(p['account'],p['folder'],p['uid']) for p in places],
                         [('imap.one|user','INBOX','7'),('imap.two|user','Archive','9')])
        self.assertTrue(all(p['first_seen'] for p in places))
        (row,)=self.a.duplicates()
        self.assertEqual((row[0],row[1]), (h,2))
        self.assertIn('imap.one|user / INBOX',row[2]); self.assertIn('imap.two|user / Archive',row[2])
        self.assertRaises(ValueError,self.a.provenance,'0'*64)
    def test_export_manifest_includes_acquisition_time(self):
        h=self.a.ingest(RAW,('imap.one|user','INBOX','1','7'))
        dest=Path(self.tmp.name)/'pkg'
        self.a.export([h],dest)
        entry=json.loads((dest/'manifest.json').read_text())[0]
        self.assertEqual(entry['origins'][0],['imap.one|user','INBOX','1','7'])
        self.assertTrue(entry['acquired'])
    def test_legacy_origins_table_gains_acquisition_column(self):
        root=Path(self.tmp.name)/'legacy-origins'; (root/'raw').mkdir(parents=True)
        raw=b'Subject: Old\r\nMessage-ID: <old@example.invalid>\r\n\r\nold body\r\n'
        digest=__import__('hashlib').sha256(raw).hexdigest()
        (root/'raw'/(digest+'.eml')).write_bytes(raw)
        legacy=sqlite3.connect(root/'archive.sqlite3')
        legacy.executescript("""CREATE TABLE messages(hash TEXT PRIMARY KEY, subject TEXT, sender TEXT, date TEXT,
            message_id TEXT, reply_to TEXT, body TEXT);
            CREATE VIRTUAL TABLE search USING fts5(hash UNINDEXED, subject, sender, body);
            CREATE TABLE origins(account TEXT, folder TEXT, validity TEXT, uid TEXT, hash TEXT NOT NULL REFERENCES messages(hash), PRIMARY KEY(account,folder,validity,uid));""")
        legacy.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(digest,'Old','','','<old@example.invalid>','','old body'))
        legacy.execute('INSERT INTO origins VALUES(?,?,?,?,?)',('imap.old|user','INBOX','3','41',digest))
        legacy.commit(); legacy.close()
        archive=Archive(root)
        try:
            places=archive.provenance(digest)
            self.assertEqual(len(places),1)
            self.assertEqual((places[0]['folder'],places[0]['uid']),('INBOX','41'))
            self.assertIsNone(places[0]['first_seen'])
            self.assertEqual(archive.duplicates(),[])
        finally: archive.db.close()
    def test_interchange_records_metadata_without_bodies(self):
        h=self.a.ingest(self.attachment_message(b'ic@example.invalid',b'rows.csv',b'text/csv'),('imap.one|user','INBOX','1','7'))
        records=list(self.a.interchange())
        self.assertEqual(len(records),1)
        record=records[0]
        self.assertEqual((record['sha256'],record['subject']), (h,'Filed'))
        self.assertNotIn('body',record)
        self.assertEqual(record['attachments'][0]['filename'],'rows.csv')
        self.assertTrue(record['attachments'][0]['sha256'])
        self.assertEqual(record['origins'][0]['account'],'imap.one|user')
        self.assertTrue(record['origins'][0]['first_seen'])
        stream=self.a.interchange()
        self.assertIs(iter(stream),stream)
    def test_interchange_supports_incremental_and_bounded_export(self):
        old=self.a.ingest(b'Subject: Old\r\nMessage-ID: <old@example.invalid>\r\n\r\nold\r\n',('imap|user','INBOX','1','1'))
        new=self.a.ingest(b'Subject: New\r\nMessage-ID: <new@example.invalid>\r\n\r\nnew\r\n',('imap|user','INBOX','1','2'))
        with self.a.db:
            self.a.db.execute("UPDATE origins SET first_seen='2024-01-01 00:00:00' WHERE hash=?",(old,))
            self.a.db.execute("UPDATE origins SET first_seen='2024-06-01 00:00:00' WHERE hash=?",(new,))
        since=[r['sha256'] for r in self.a.interchange(since='2024-03-01 00:00:00')]
        self.assertEqual(since,[new])
        self.assertEqual([r['sha256'] for r in self.a.interchange(limit=1)],[old])
        self.assertEqual([r['sha256'] for r in self.a.interchange(since='2030-01-01 00:00:00')],[])
    def test_interchange_command_writes_portable_manifest(self):
        h=self.a.ingest(RAW,('imap.one|user','INBOX','1','7'))
        dest=Path(self.tmp.name)/'manifest.json'
        out=io.StringIO()
        with mock.patch('sys.argv',['dispatch.py','--archive',str(self.a.root),'interchange',str(dest)]), contextlib.redirect_stdout(out):
            self.assertEqual(main(),0)
        document=json.loads(dest.read_text())
        self.assertEqual(document['format'],'hb-dispatch-interchange-1')
        self.assertEqual([r['sha256'] for r in document['messages']],[h])
        self.assertEqual(document['messages'][0]['origins'][0]['folder'],'INBOX')
        self.assertRaises(FileExistsError,self.a.export_mbox,[h],dest)
    def test_version_flag(self):
        out=io.StringIO()
        with mock.patch('sys.argv',['dispatch.py','--version']), contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as exit:
                main()
        self.assertEqual(exit.exception.code,0)
        self.assertEqual(out.getvalue().strip(),f'dispatch.py {__version__}')
if __name__=='__main__': unittest.main()
