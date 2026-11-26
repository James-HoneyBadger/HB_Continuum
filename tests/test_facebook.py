# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import json, tempfile, unittest
from pathlib import Path
from facebook import preview, import_files, _expand, _extract_items, _normalize
from catalog import Catalog

class FacebookImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'archive'
        self.root.mkdir()
    def tearDown(self):
        self.tmp.cleanup()
    def write(self, name, doc):
        path=self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False))
        return path

    def test_preview_posts_list(self):
        path=self.write('your_posts_1.json',[
            {'timestamp': 1700000000, 'data': [{'post': 'Hello world'}]},
            {'timestamp': 1700000001, 'data': [{'post': 'Second post'}]},
        ])
        result=preview([str(path)])
        self.assertEqual(result['files_discovered'],1)
        self.assertEqual(result['estimated_records'],2)
        self.assertEqual(result['supported_records'],2)
        self.assertEqual(result['unsupported_records'],0)

    def test_import_posts_and_resume(self):
        path=self.write('your_posts_1.json',[
            {'timestamp': 1700000000, 'data': [{'post': 'Hello world'}]},
            {'timestamp': 1700000001, 'data': [{'post': 'Second post'}]},
        ])
        first=import_files([str(path)], self.root)
        self.assertEqual(first['files_imported'],1)
        self.assertEqual(first['records_encountered'],2)
        self.assertEqual(first['records_imported'],2)
        self.assertEqual(first['records_duplicate'],0)
        second=import_files([str(path)], self.root)
        self.assertEqual(second['files_skipped'],1)
        self.assertEqual(second['records_imported'],0)
        catalog=Catalog(self.root)
        try:
            self.assertEqual(catalog.stats()['records'],2)
        finally:
            catalog.close()

    def test_import_messages_preserves_original(self):
        path=self.write('messages/inbox/Example Person/message_1.json',{
            'title': 'Example Person',
            'participants': [{'name': 'Example Person'}],
            'messages': [
                {'sender_name': 'Example Person', 'timestamp_ms': 1700000000123,
                 'content': 'Are we meeting tomorrow?'},
                {'sender_name': 'Owner', 'timestamp_ms': 1700000005000,
                 'content': 'Yes, at noon.'},
            ],
        })
        result=import_files([str(path)], self.root)
        self.assertEqual(result['records_imported'],2)
        catalog=Catalog(self.root)
        try:
            rows=catalog.db.execute(
                'SELECT record_kind,actor,occurred_precision,body,original_json FROM records ORDER BY occurred_at').fetchall()
            self.assertEqual([r[0] for r in rows],['message','message'])
            self.assertEqual(rows[0][1],'Example Person')
            self.assertEqual(rows[0][2],'ms')
            self.assertEqual(rows[0][3],'Are we meeting tomorrow?')
            self.assertEqual(json.loads(rows[0][4])['sender_name'],'Example Person')
        finally:
            catalog.close()

    def test_comments_and_group_posts(self):
        comments=self.write('comments.json',{'comments':[
            {'timestamp': 1700000100, 'data': [{'comment': {'comment': 'Nice post', 'timestamp': 1700000100}}]},
        ]})
        groups=self.write('your_posts_in_groups.json',{'your_posts_in_groups':[
            {'timestamp': 1700000200, 'data': [{'post': 'Group announcement'}]},
        ]})
        result=import_files([str(comments), str(groups)], self.root)
        self.assertEqual(result['files_imported'],2)
        self.assertEqual(result['records_imported'],2)
        catalog=Catalog(self.root)
        try:
            kinds={r[0] for r in catalog.db.execute('SELECT record_kind FROM records')}
            self.assertEqual(kinds,{'comment','post'})
            keys={r[0] for r in catalog.db.execute('SELECT source_key FROM records')}
            self.assertEqual(keys,{'comments','your_posts_in_groups'})
        finally:
            catalog.close()

    def test_duplicate_overlap(self):
        shared={'timestamp': 1700000000, 'data': [{'post': 'Shared'}]}
        first=self.write('posts_a.json',{'your_posts':[shared]})
        second=self.write('posts_b.json',{'your_posts':[
            shared,
            {'timestamp': 1700000001, 'data': [{'post': 'Only in second export'}]},
        ]})
        result=import_files([str(first), str(second)], self.root)
        self.assertEqual(result['files_imported'],2)
        self.assertEqual(result['records_imported'],2)
        self.assertEqual(result['records_duplicate'],1)

    def test_malformed_and_unsupported(self):
        bad=self.root/'bad.json'
        bad.write_text('{not json')
        places=self.write('your_places.json',{'your_places':[{'name':'Home','coordinate':{}}]})
        result=import_files([str(bad), str(places)], self.root)
        self.assertEqual(result['parse_errors'],1)
        self.assertEqual(result['files_unsupported'],1)
        self.assertEqual(result['files_imported'],0)
        self.assertEqual(len(result['warnings']),2)

    def test_expand_skips_hidden(self):
        visible=self.root/'posts.json'; visible.write_text('[]')
        hidden=self.root/'.hidden'; hidden.mkdir()
        (hidden/'secret.json').write_text('[]')
        self.assertEqual(_expand([str(self.root)]),[visible])

    def test_normalize_missing_timestamp(self):
        item={'data': [{'post': 'No date'}]}
        record=_normalize('posts', item)
        self.assertEqual(record['occurred_at'],None)
        self.assertEqual(record['occurred_precision'],'unknown')
        self.assertEqual(record['body'],'No date')

    def test_extract_items_top_level_list(self):
        category,key,items=_extract_items(Path('your_posts_1.json'),[
            {'timestamp': 1, 'data': [{'post': 'x'}]},
        ])
        self.assertEqual((category,key,len(items)),('posts','posts',1))

    def test_event_import(self):
        path=self.write('your_events.json',{'your_events':[
            {'name': 'Book club', 'start_timestamp': 1700000300,
             'description': 'Discussing chapter three'},
        ]})
        result=import_files([str(path)], self.root)
        self.assertEqual(result['files_imported'],1)
        self.assertEqual(result['records_imported'],1)
        catalog=Catalog(self.root)
        try:
            row=catalog.db.execute('SELECT record_kind,occurred_precision,body FROM records').fetchone()
            self.assertEqual(row[0],'event')
            self.assertEqual(row[1],'second')
            self.assertIn('Book club',row[2])
        finally:
            catalog.close()

    def test_search_and_list(self):
        path=self.write('your_posts_1.json',{'your_posts':[
            {'timestamp': 1700000000, 'data': [{'post': 'Bullion receipt'}]},
            {'timestamp': 1700000001, 'data': [{'post': 'Another note'}]},
        ]})
        import_files([str(path)], self.root)
        catalog=Catalog(self.root)
        try:
            hits=catalog.search_records('bullion')
            self.assertEqual(len(hits),1)
            self.assertEqual(hits[0][5],'Bullion receipt')
            self.assertEqual(catalog.search_records('a:b'),[])
            self.assertEqual(catalog.search_records('*'),[])
            listed=catalog.list_records('facebook', record_kind='post', limit=10)
            self.assertEqual(len(listed),2)
            self.assertEqual(catalog.list_records('facebook', record_kind='message'),[])
        finally:
            catalog.close()

    def test_migration_upgrades_v1(self):
        import sqlite3
        from catalog import MIGRATIONS
        path=self.root/'catalog.sqlite3'
        conn=sqlite3.connect(path)
        for stmt in MIGRATIONS[1]:
            conn.execute(stmt)
        conn.execute('PRAGMA user_version=1')
        conn.execute("INSERT INTO source_files VALUES('h','facebook','posts','p',1,'now')")
        conn.execute("INSERT INTO records VALUES('r','facebook','posts','post',NULL,NULL,'second','hello',NULL,'h','now')")
        conn.commit()
        conn.close()
        catalog=Catalog(self.root)
        try:
            self.assertEqual(catalog.db.execute('PRAGMA user_version').fetchone()[0],2)
            self.assertEqual(catalog.stats()['records'],1)
            self.assertEqual(len(catalog.search_records('hello')),1)
        finally:
            catalog.close()

    def test_media_import(self):
        path=self.write('your_videos.json',[
            {'title': 'Trip video', 'creation_timestamp': 1700000400},
        ])
        result=import_files([str(path)], self.root)
        self.assertEqual(result['files_imported'],1)
        self.assertEqual(result['records_imported'],1)
        catalog=Catalog(self.root)
        try:
            row=catalog.db.execute('SELECT record_kind,occurred_precision,body FROM records').fetchone()
            self.assertEqual(row[0],'media')
            self.assertEqual(row[1],'second')
            self.assertIn('Trip video',row[2])
        finally:
            catalog.close()

    def test_reactions_import(self):
        path=self.write('likes_and_reactions/posts_and_comments.json',{'reactions':[
            {'timestamp': 1700000500, 'title': 'Some post',
             'data': [{'reaction': {'reaction': 'LIKE', 'actor': 'Alice'}}]},
        ]})
        result=import_files([str(path)], self.root)
        self.assertEqual(result['files_imported'],1)
        self.assertEqual(result['records_imported'],1)
        catalog=Catalog(self.root)
        try:
            row=catalog.db.execute('SELECT record_kind,actor,body FROM records').fetchone()
            self.assertEqual(row[0],'reaction')
            self.assertEqual(row[1],'Alice')
            self.assertIn('LIKE',row[2])
        finally:
            catalog.close()

if __name__=='__main__':
    unittest.main()
