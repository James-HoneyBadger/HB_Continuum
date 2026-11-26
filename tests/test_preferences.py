import tempfile, unittest
from pathlib import Path
from unittest import mock
from preferences import DEFAULTS,validate,load,save,decode,export
from dispatch import Archive

class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_defaults(self):self.assertEqual(load(self.root),DEFAULTS)
    def test_roundtrip(self):
        save(self.root,{'theme':'Dark','search_limit':350,'show_hash':False})
        p=load(self.root);self.assertEqual(p['theme'],'Dark');self.assertEqual(p['search_limit'],350);self.assertFalse(p['show_hash'])
        dest=self.root/'portable.json';export(dest,p)
        import json
        self.assertEqual(decode(json.loads(dest.read_text())),p)
    def test_reject_invalid(self):
        for p in ({'font_size':100},{'search_limit':True},{'theme':'unknown'},{'password':'secret'},{'startup_view':'Saved query'}):
            with self.assertRaises(ValueError):validate(p)
        with self.assertRaises(ValueError):decode({'version':2,'preferences':{}})
    def test_sync_preferences(self):
        ar=Archive(self.root)
        try:
            save(self.root,{'network_timeout':90,'batch_limit':1})
            m=mock.MagicMock();m.__enter__.return_value=m
            m.select.return_value=('OK',[b'2']);m.response.return_value=('UIDVALIDITY',[b'1'])
            m.uid.side_effect=[('OK',[b'1 2']),('OK',[(b'1',b'Subject: test\r\n\r\nbody')])]
            with mock.patch('dispatch.imaplib.IMAP4_SSL',return_value=m) as connect:
                self.assertEqual(ar.sync('host','user','pw'),1)
                self.assertEqual(connect.call_args.kwargs['timeout'],90)
            self.assertEqual(ar.stats()['origins'],1)
        finally:ar.db.close()
