import unittest,tempfile
from pathlib import Path
from email.message import EmailMessage
from dispatch import Archive
from backup import backup,restore,validate_snapshot
from mime_index import html_text
class Hardening(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.a=Archive(self.root/'archive')
    def tearDown(self):self.a.db.close();self.t.cleanup()
    def test_html_no_active_content(self):
        h=self.a.ingest(b'Subject: test\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>uniqueinvoice</p><script>secretcode</script><img src="https://invalid.example">')
        self.assertEqual(self.a.find('uniqueinvoice')[0][0],h)
        self.assertEqual(self.a.find('secretcode'),[])
        self.assertNotIn('https://',self.a.details(h)['body'])
    def test_attachments(self):
        m=EmailMessage();m['Subject']='Receipt';m.set_content('body')
        m.add_attachment(b'raretransaction',maintype='text',subtype='plain',filename='statement.txt')
        m.add_attachment(b'opaque',maintype='application',subtype='pdf',filename='invoice.pdf')
        h=self.a.ingest(m.as_bytes())
        self.assertEqual(self.a.find('raretransaction')[0][0],h)
        self.assertEqual(len(self.a.attachments(h)),2)
        self.assertEqual(self.a.find('invoice')[0][0],h)
        self.assertEqual(self.a.verify(),[])
    def test_reindex_existing(self):
        h=self.a.ingest(b'Content-Type: text/html\r\n\r\n<p>historicword</p>')
        with self.a.db:
            self.a.db.execute('DELETE FROM extraction_versions')
            self.a.db.execute('UPDATE messages SET body=""')
            self.a.db.execute('UPDATE search SET body=""')
        self.assertEqual(self.a.reindex(),1)
        self.assertEqual(self.a.reindex(),0)
        self.assertEqual(self.a.find('historicword')[0][0],h)
        self.assertEqual(self.a.verify(),[])
    def test_backup_restore(self):
        h=self.a.ingest(b'Subject: preserved\r\n\r\nhello')
        snap=self.root/'snapshot';dest=self.root/'restored'
        self.assertTrue(backup(self.a.root,snap)['verified'])
        self.assertTrue(restore(snap,dest)['verified'])
        b=Archive(dest)
        try:
            self.assertEqual(b.verify(),[])
            self.assertEqual(b.find('preserved')[0][0],h)
        finally:b.db.close()
        with self.assertRaises(FileExistsError):restore(snap,dest)
        (snap/'raw'/(h+'.eml')).write_bytes(b'changed')
        with self.assertRaises(ValueError):validate_snapshot(snap)
    def test_backup_refuses_bad_raw(self):
        h=self.a.ingest(b'Subject: test\r\n\r\nhello')
        (self.a.raw/(h+'.eml')).write_bytes(b'bad')
        with self.assertRaises(ValueError):backup(self.a.root,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_health_reconciles(self):
        h=self.a.ingest(b'Subject: one\r\n\r\nbody')
        self.assertTrue(self.a.health()['sqlite_ok'])
        self.assertEqual(self.a.health()['index_missing'],[])
        with self.a.db:self.a.db.execute('DELETE FROM search WHERE hash=?',(h,))
        self.assertEqual(self.a.health()['index_missing'],[h])
        self.assertEqual(self.a.verify(),[])
    def test_ingest_busy(self):
        from sync_lock import sync_lock,SyncBusy
        with sync_lock(self.a.root):
            with self.assertRaises(SyncBusy):self.a.ingest(b'Subject: busy')
        self.assertEqual(self.a.stats()['messages'],0)
    def test_snapshot_rejects_extra_and_symlink(self):
        self.a.ingest(b'Subject: one')
        snap=self.root/'snap';backup(self.a.root,snap)
        (snap/'bad').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):validate_snapshot(snap)
    def test_restore_pauses_profiles(self):
        import json
        self.a.ingest(b'Subject: one')
        (self.a.root/'schedule.json').write_text(json.dumps({'sample':{'enabled':True}}))
        snap=self.root/'snap';dest=self.root/'restored';backup(self.a.root,snap);restore(snap,dest)
        self.assertFalse(json.loads((dest/'schedule.json').read_text())['sample']['enabled'])
    def test_symlink_raw_is_rejected(self):
        h=self.a.ingest(b'Subject: one')
        source=self.a.raw/(h+'.eml');target=self.root/'outside'
        source.rename(target);source.symlink_to(target)
        self.assertEqual(self.a.verify(),[h])
        with self.assertRaises(ValueError):self.a.export([h],self.root/'export')

    def test_orphan_recovery(self):
        import hashlib
        raw=b'Subject: recovered\r\n\r\nbody'
        h=hashlib.sha256(raw).hexdigest()
        (self.a.raw/(h+'.eml')).write_bytes(raw)
        self.assertEqual(self.a.health()['raw_unindexed'],[h])
        self.assertEqual(self.a.recover_orphans(),[h])
        self.assertEqual(self.a.recover_orphans(),[])
        self.assertEqual(self.a.health()['raw_unindexed'],[])
        self.assertEqual(self.a.stats(),{'messages':1,'origins':0})
