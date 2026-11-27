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

    def test_date_range_filters_both_sources(self):
        self.a.ingest(b'From: b@example.invalid\r\nSubject: Bullion later\r\n'
                      b'Date: Tue, 02 Jan 2024 00:00:00 +0000\r\n\r\nbullion')
        # The Facebook fixture is timestamped 2023-11-14; a 2024 window excludes it.
        results=search_unified(self.root, 'bullion', after=1704067200)
        self.assertEqual({r['source'] for r in results},{'email'})
        self.assertTrue(all(r['source']=='email' for r in results))
        self.assertEqual(search_unified(self.root, 'bullion', after=1704067200, before=1704153600),[]) 

    def test_sender_and_kind_filters(self):
        email_only=search_unified(self.root,'bullion',senders=['a@example.invalid'])
        self.assertEqual({r['source'] for r in email_only},{'email'})
        catalog_only=search_unified(self.root,'bullion',kinds=['post'])
        self.assertEqual({r['source'] for r in catalog_only},{'facebook'})
        messages_only=search_unified(self.root,'bullion',kinds=['message'])
        self.assertEqual({r['source'] for r in messages_only},{'email'})
        self.assertEqual(search_unified(self.root,'bullion',kinds=['reaction']),[])

    def test_tag_filter_reads_the_research_overlay(self):
        from research import Research
        research=Research(self.a)
        try:
            research.tag(self.a.find('bullion')[0][0],'important')
        finally:
            research.close()
        results=search_unified(self.root,'bullion',tags=['important'])
        self.assertEqual({r['source'] for r in results},{'email'})
        self.assertEqual(len(results),1)

    def test_query_validation_explains_rejections(self):
        from unified import validate_query
        self.assertTrue(validate_query(self.root,'bullion')['valid'])
        self.assertTrue(validate_query(self.root,'"bull ion"')['valid'])
        bad=validate_query(self.root,'a:b')
        self.assertFalse(bad['valid'])
        self.assertIn('AND/OR/NOT',bad['message'])
        self.assertFalse(validate_query(self.root,'   ')['valid'])

    def test_exact_counts(self):
        from unified import search_unified_count
        self.assertEqual(search_unified_count(self.root,'bullion'),2)
        self.assertEqual(search_unified_count(self.root,'bullion',sources=('email',)),1)
        self.assertEqual(search_unified_count(self.root,'bullion',kinds=['post']),1)
        self.assertIsNone(search_unified_count(self.root,'bullion',tags=['important']))

    def test_relevance_orders_more_specific_matches_first(self):
        self.a.ingest(b'From: a@example.invalid\r\nSubject: Bullion\r\n\r\nBullion bullion bullion')
        results=search_unified(self.root, 'bullion', sources=('email',))
        self.assertEqual(len(results),2)
        self.assertIn('bullion bullion bullion', results[0]['snippet'].lower())

if __name__=='__main__':
    unittest.main()
