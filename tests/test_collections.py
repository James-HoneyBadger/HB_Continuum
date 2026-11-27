# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Curated evidence collections: membership, metadata and manifests."""
import json, tempfile, unittest
from pathlib import Path
from dispatch import Archive
from research import Research
from catalog import Catalog
from facebook import import_files as facebook_import
from reporting import (build_collection_manifest, render_collection,
                       write_collection_manifest)

def message():
    return (b'From: a@example.invalid\r\nSubject: Key evidence\r\n'
            b'Date: Mon, 01 Jan 2024 10:00:00 +0000\r\n\r\nbody')

class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.archive=Archive(self.root)
        self.email=self.archive.ingest(message())
        export=self.root/'posts.json'
        export.write_text(json.dumps({'your_posts':[
            {'timestamp':1700000000,'data':[{'post':'Catalog evidence'}]}]}))
        facebook_import([str(export)],self.root)
        catalog=Catalog(self.root)
        try:
            self.record=catalog.db.execute('SELECT record_id FROM records LIMIT 1').fetchone()[0]
        finally:
            catalog.close()
        self.research=Research(self.archive)
        self.collection=self.research.collection_create('General','Case file','Investigation')

    def tearDown(self):
        self.research.close(); self.archive.db.close(); self.tmp.cleanup()

    def test_create_list_and_duplicate_name(self):
        self.assertEqual(self.collection['name'],'Case file')
        listed=self.research.collection_list()
        self.assertEqual([row['name'] for row in listed],['Case file'])
        self.assertEqual(listed[0]['item_count'],0)
        with self.assertRaises(ValueError):
            self.research.collection_create('General','Case file')
        with self.assertRaises(ValueError):
            self.research.collection_create('Missing','Other')

    def test_add_resolves_record_metadata(self):
        self.research.collection_add(self.collection['id'],'email',self.email,note='primary')
        self.research.collection_add(self.collection['id'],'catalog',self.record)
        full=self.research.collection_get(self.collection['id'])
        self.assertEqual(full['item_count'],2)
        by_type={item['item_type']:item for item in full['items']}
        self.assertEqual(by_type['email']['title'],'Key evidence')
        self.assertTrue(by_type['email']['exists'])
        self.assertEqual(by_type['email']['note'],'primary')
        self.assertEqual(by_type['catalog']['kind'],'post')
        self.assertTrue(by_type['catalog']['exists'])

    def test_unknown_items_are_rejected(self):
        with self.assertRaises(ValueError):
            self.research.collection_add(self.collection['id'],'email','0'*64)
        with self.assertRaises(ValueError):
            self.research.collection_add(self.collection['id'],'catalog','missing')
        with self.assertRaises(ValueError):
            self.research.collection_add(self.collection['id'],'photo','x')
        with self.assertRaises(ValueError):
            self.research.collection_add(self.collection['id'],'email',self.email,'x'*2001)

    def test_remove_item_and_delete_collection_cascades(self):
        self.research.collection_add(self.collection['id'],'email',self.email)
        removed=self.research.collection_remove(self.collection['id'],'email',self.email)
        self.assertEqual(removed['item_count'],0)
        self.research.collection_add(self.collection['id'],'email',self.email)
        self.research.collection_delete(self.collection['id'])
        self.assertEqual(self.research.collection_list(),[])
        self.assertEqual(self.research.db.execute(
            'SELECT count(*) FROM collection_items').fetchone()[0],0)
        with self.assertRaises(ValueError):
            self.research.collection_get(self.collection['id'])

    def test_missing_record_is_reported_not_dropped(self):
        self.research.collection_add(self.collection['id'],'email',self.email)
        with self.archive.db:
            self.archive.db.execute('DELETE FROM attachment_index WHERE hash=?',(self.email,))
            self.archive.db.execute('DELETE FROM extraction_versions WHERE hash=?',(self.email,))
            self.archive.db.execute('DELETE FROM search WHERE hash=?',(self.email,))
            self.archive.db.execute('DELETE FROM messages WHERE hash=?',(self.email,))
        full=self.research.collection_get(self.collection['id'])
        self.assertEqual(full['item_count'],1)
        self.assertFalse(full['items'][0]['exists'])
        manifest=build_collection_manifest(full)
        self.assertFalse(manifest['items'][0]['exists'])
        self.assertIn('(missing)',render_collection(manifest,'markdown'))

    def test_manifest_renders_json_markdown_and_refuses_overwrite(self):
        self.research.collection_add(self.collection['id'],'email',self.email,note='primary')
        manifest=build_collection_manifest(self.research.collection_get(self.collection['id']))
        markdown=render_collection(manifest,'markdown')
        self.assertIn('Evidence manifest: Case file',markdown)
        self.assertIn(self.email,markdown)
        self.assertIn('primary',markdown)
        payload=json.loads(render_collection(manifest,'json'))
        self.assertEqual(payload['items'][0]['item_id'],self.email)
        destination=Path(self.tmp.name)/'manifest.md'
        result=write_collection_manifest(manifest,'markdown',destination)
        self.assertEqual(result['format'],'markdown')
        with self.assertRaises(FileExistsError):
            write_collection_manifest(manifest,'markdown',destination)
        with self.assertRaises(ValueError):
            render_collection(manifest,'html')

if __name__=='__main__':
    unittest.main()
