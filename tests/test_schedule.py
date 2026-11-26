import tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from dispatch import Archive
from schedule import profile,due,tick,write_json,read_json,service
from sync_lock import sync_lock,SyncBusy

class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,11,26,12,0,tzinfo=timezone.utc)
        self.p=profile('mail','imap.gmail.com','user@example.invalid',['[Gmail]/All Mail'],minutes=30)
    def tearDown(self): self.tmp.cleanup()
    def test_interval(self):
        self.assertTrue(due(self.p,{},self.now))
        state={'last_attempt':self.now.isoformat()}
        self.assertFalse(due(self.p,state,self.now+timedelta(minutes=29)))
        self.assertTrue(due(self.p,state,self.now+timedelta(minutes=30)))
        self.assertFalse(due(dict(self.p,enabled=False),{},self.now))
    def test_daily(self):
        p=profile('mail','imap.example.invalid','user',['INBOX'],daily='12:00')
        local=datetime.now().astimezone().replace(hour=12,minute=0,second=0,microsecond=0)
        self.assertFalse(due(p,{},local-timedelta(minutes=1)))
        self.assertTrue(due(p,{},local))
        self.assertFalse(due(p,{'last_attempt':local.isoformat()},local+timedelta(minutes=1)))
    def test_validation(self):
        for kw in ({'minutes':1},{'daily':'25:00'},{'minutes':30,'daily':'12:00'},{}):
            with self.assertRaises(ValueError):profile('a','host','user',['INBOX'],**kw)
    def test_run_and_skip(self):
        write_json(self.root/'schedule.json',{'mail':self.p})
        with mock.patch.object(Archive,'sync',return_value=7) as s:
            result=tick(self.root,now=self.now,get_password=lambda p:'fake-secret')
            self.assertEqual(result['mail']['imported'],7)
            self.assertEqual(result['mail']['status'],'ok')
            s.assert_called_once_with('imap.gmail.com','user@example.invalid','fake-secret','[Gmail]/All Mail')
            tick(self.root,now=self.now,get_password=lambda p:'fake-secret')
            self.assertEqual(s.call_count,1)
        self.assertNotIn('fake-secret',(self.root/'schedule-status.json').read_text())
    def test_failure_isolated(self):
        write_json(self.root/'schedule.json',{'mail':self.p,'other':dict(self.p,name='other',user='other')})
        def pw(p):
            if p['name']=='mail': raise RuntimeError('secret should not be logged')
            return 'synthetic'
        with mock.patch.object(Archive,'sync',return_value=1):
            r=tick(self.root,now=self.now,get_password=pw)
        self.assertEqual(r['mail']['status'],'error: RuntimeError')
        self.assertEqual(r['other']['status'],'ok')
        self.assertNotIn('secret should not be logged',(self.root/'schedule-status.json').read_text())
    def test_busy_defers_without_consuming_schedule(self):
        write_json(self.root/'schedule.json',{'mail':self.p})
        with sync_lock(self.root):
            result=tick(self.root,now=self.now,get_password=lambda p:'fake')
        self.assertEqual(result['mail']['status'],'deferred: archive busy')
        self.assertNotIn('last_attempt',result['mail'])
    def test_legacy_gmail_folder(self):
        ar=Archive(self.root)
        try:
            ar.ingest(b'Subject: test\r\n\r\nbody',('imap.gmail.com|user','"[Gmail]/All Mail"','7','42'))
            m=mock.MagicMock();m.__enter__.return_value=m
            m.select.return_value=('OK',[b'1']);m.response.return_value=('UIDVALIDITY',[b'7'])
            m.uid.return_value=('OK',[b'42'])
            with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m):
                self.assertEqual(ar.sync('imap.gmail.com','user','abcd efgh ijkl mnop','[Gmail]/All Mail'),0)
            m.login.assert_called_once_with('user','abcdefghijklmnop')
            m.select.assert_called_once_with('"[Gmail]/All Mail"',readonly=True)
            m.uid.assert_called_once_with('search',None,'ALL')
        finally:ar.db.close()
