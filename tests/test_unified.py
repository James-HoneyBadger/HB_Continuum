# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import json, tempfile, unittest
from pathlib import Path
from dispatch import Archive
from facebook import import_files
from unified import search_unified

class UnifiedSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.a=Archive(self.root)
        self.a.ingest(b'From: a@example.invalid\r\nSubject: Silver invoice\r\n\r\nBullion receipt')
        posts=self.root/'posts.json'
        posts.write_text(json.dumps({'your_posts':[
            {'timestamp': 1700000000, 'data': [{'post': 'Bought bullion from the dealer'}]},
        ]}))
        import_files([str(posts)], self.root)
    def tearDown(self):
        self.a.db.close(); self.tmp.cleanup()

    def test_searches_both_sources(self):
        results=search_unified(self.root, 'bullion')
        self.assertEqual({r['source'] for r in results},{'email','facebook'})
        email=[r for r in results if r['source']=='email'][0]
        facebook=[r for r in results if r['source']=='facebook'][0]
        self.assertEqual(email['kind'],'message')
        self.assertEqual(facebook['kind'],'post')
        self.assertIn('Bullion receipt',email['snippet'])
        self.assertIn('Bought bullion',facebook['snippet'])

    def test_source_filter(self):
        results=search_unified(self.root, 'bullion', sources=('facebook',))
        self.assertEqual({r['source'] for r in results},{'facebook'})

    def test_malformed_query_returns_empty(self):
        for q in ('a:b','-invoice','*','"unterminated'):
            self.assertIsInstance(search_unified(self.root, q),list)
        self.assertEqual(search_unified(self.root, 'a:b'),[])

    def test_limit(self):
        self.a.ingest(b'From: b@example.invalid\r\nSubject: Another bullion note\r\n\r\nMore bullion')
        self.assertEqual(len(search_unified(self.root, 'bullion', limit=1)),1)

if __name__=='__main__':
    unittest.main()
