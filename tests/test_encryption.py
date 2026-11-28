# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Encrypted archive creation, unlock, locking and protected artifacts."""
import contextlib
import io
import os
import sqlite3
import stat
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from hb_engine import db, encryption, migrations
from hb_engine.ipc import IPCServer, PROTOCOL_VERSION
from hb_engine.catalog import Catalog
from hb_engine.documents import import_files as import_documents
from hb_engine.dispatch import Archive
from hb_engine.intelligence import ConversationStore
from hb_engine.research import Research
from hb_engine.unified import search_unified

PASSWORD = 'correct horse battery staple'


class EncryptedArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'encrypted'
        if not db.encryption_available():
            self.skipTest('optional sqlcipher3 binding is not installed')

    def tearDown(self):
        try:
            db.clear_session_key(self.root)
        finally:
            self.tmp.cleanup()

    def test_creation_rejects_existing_destination_and_short_password(self):
        with self.assertRaises(encryption.EncryptionError):
            encryption.create(self.root, 'short')
        self.root.mkdir()
        (self.root / 'unrelated').write_text('not an archive')
        with self.assertRaises(encryption.EncryptionError):
            encryption.create(self.root, PASSWORD)

    def test_creation_unlock_lock_and_synthetic_research(self):
        result = encryption.create(self.root, PASSWORD)
        self.assertTrue(result['encrypted'])
        self.assertTrue(result['unlocked'])
        descriptor = self.root / encryption.DESCRIPTOR_NAME
        self.assertTrue(descriptor.is_file())
        self.assertEqual(stat.S_IMODE(descriptor.stat().st_mode), 0o600)
        raw_descriptor = descriptor.read_text(encoding='utf-8')
        self.assertNotIn(PASSWORD, raw_descriptor)
        for name in encryption.DATABASES:
            path = self.root / name
            self.assertTrue(db.is_encrypted_file(path), name)
            conn = sqlite3.connect(path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
            finally:
                conn.close()

        archive = Archive(self.root)
        digest = archive.ingest(
            b'From: a@example.invalid\r\nSubject: encrypted evidence\r\n'
            b'Date: Thu, 26 Nov 2026 09:00:00 +0000\r\n\r\nsecret needle')
        raw = self.root / 'raw' / (digest + '.eml')
        self.assertIn(b'secret needle', raw.read_bytes())
        hits = search_unified(self.root, 'needle')
        self.assertEqual(hits[0]['source'], 'email')
        catalog = Catalog(self.root)
        try:
            with catalog.db:
                catalog.add_file('doc-hash', 'document', 'note.txt',
                                 '/tmp/note.txt', 1, '2026-11-28')
                catalog.add_record(
                    'doc1', 'document', 'note.txt', 'document', None,
                    '2026-11-28T00:00:00+00:00', 'second', 'secret document evidence',
                    '{}', 'doc-hash', '2026-11-28')
        finally:
            catalog.close()
        self.assertEqual(search_unified(self.root, 'secret', sources=('document',))[0]['id'],
                         'doc1')
        external = Path(self.tmp.name) / 'external.txt'
        external.write_text('external document stays plaintext', encoding='utf-8')
        before = external.read_bytes()
        imported = import_documents([str(external)], self.root)
        self.assertEqual(imported['records_imported'], 1)
        self.assertEqual(external.read_bytes(), before)
        self.assertFalse((self.root / 'external.txt').exists())
        self.assertEqual(search_unified(self.root, 'external', sources=('document',))[0]['source'],
                         'document')
        research = Research(archive)
        try:
            research.workspace('Synthetic', 'encrypted test workspace')
        finally:
            research.close()
        conversation = ConversationStore(self.root)
        try:
            saved = conversation.create('Synthetic', 'Encrypted conversation')
            conversation.append(saved['id'], 'user', 'What is documented?')
        finally:
            conversation.close()
        self.assertEqual(migrations.apply(archive.db, 'archive')['applied'], [])
        conn = db.connect(self.root / 'archive.sqlite3')
        try:
            self.assertEqual(conn.execute('PRAGMA temp_store').fetchone()[0], 2)
            self.assertEqual(conn.execute('PRAGMA secure_delete').fetchone()[0], 1)
        finally:
            conn.close()
        archive.db.close()

        with self.assertRaises(ValueError):
            from hb_engine import backup
            backup.backup(self.root, self.root.parent / 'snapshot')

        locked = encryption.lock(self.root)
        self.assertFalse(locked['unlocked'])
        with self.assertRaises(Exception):
            Archive(self.root)
        with self.assertRaises(encryption.EncryptionError):
            encryption.unlock(self.root, 'wrong password')
        unlocked = encryption.unlock(self.root, PASSWORD)
        self.assertTrue(unlocked['unlocked'])
        self.assertEqual(search_unified(self.root, 'needle')[0]['source'], 'email')
        conversation = ConversationStore(self.root)
        try:
            self.assertEqual(conversation.list('Synthetic')[0]['turns'], 1)
        finally:
            conversation.close()
        self.assertTrue(encryption.lock(self.root)['unlocked'] is False)

    def test_cli_creation_and_password_prompt_unlock(self):
        from hb_engine import dispatch as dispatch_module
        output = io.StringIO()
        with mock.patch('getpass.getpass', side_effect=[PASSWORD, PASSWORD]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(dispatch_module.main(
                ['--archive', str(self.root), 'init-encrypted']), 0)
        self.assertTrue((self.root / 'archive.sqlite3').is_file())
        encryption.lock(self.root)
        with mock.patch('getpass.getpass', side_effect=[PASSWORD]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch_module.main(
                ['--archive', str(self.root), 'search', 'needle']), 0)
        encryption.lock(self.root)
        error = io.StringIO()
        with mock.patch('getpass.getpass', side_effect=['wrong password']), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(error):
            self.assertEqual(dispatch_module.main(
                ['--archive', str(self.root), 'search', 'needle']), 1)
        self.assertIn('incorrect password', error.getvalue())

    def test_ipc_unlock_and_explicit_lock(self):
        encryption.create(self.root, PASSWORD)
        encryption.lock(self.root)
        server = IPCServer(self.root, out=io.StringIO())
        def request(method, **params):
            return server.handle({'protocol_version': PROTOCOL_VERSION,
                                  'request_id': '1', 'method': method,
                                  'params': params})
        self.assertEqual(request('encryption_status')['result']['encrypted'], True)
        self.assertEqual(request('encryption_status')['result']['unlocked'], False)
        self.assertIn('error', request('stats'))
        self.assertEqual(request('encryption_unlock', password='wrong')
                         ['error']['code'], 'UNLOCK_FAILED')
        self.assertTrue(request('encryption_unlock', password=PASSWORD)
                        ['result']['unlocked'])
        self.assertEqual(request('encryption_status')['result']['unlocked'], True)
        self.assertIn('archive', request('stats')['result'])
        self.assertEqual(request('encryption_lock')['result']['unlocked'], False)
        self.assertEqual(request('encryption_status')['result']['unlocked'], False)

    def test_database_copy_and_journal_do_not_expose_plaintext(self):
        encryption.create(self.root, PASSWORD)
        copy = Path(self.tmp.name) / 'copy.sqlite3'
        copy.write_bytes((self.root / 'archive.sqlite3').read_bytes())
        conn = sqlite3.connect(copy)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
        finally:
            conn.close()
        conn = db.connect(self.root / 'archive.sqlite3')
        try:
            conn.execute('CREATE TABLE journal_probe(body TEXT)')
            marker = 'JOURNALPLAINTEXTMARKER'
            conn.execute('BEGIN')
            conn.execute('INSERT INTO journal_probe VALUES (?)', (marker,))
            journals = list(self.root.glob('*journal*'))
            self.assertTrue(journals)
            for journal in journals:
                self.assertNotIn(marker.encode('utf-8'), journal.read_bytes())
            conn.rollback()
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
