# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Synthetic plaintext-to-encrypted archive migration and failure handling."""
import contextlib
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hb_engine import db, encryption, migration
from hb_engine.catalog import Catalog
from hb_engine.dispatch import Archive
from hb_engine.intelligence import ConversationStore
from hb_engine.research import Research
from hb_engine.unified import search_unified

PASSWORD = 'migration password for tests'


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        if not db.encryption_available():
            self.skipTest('optional sqlcipher3 binding is not installed')
        archive = Archive(self.source)
        self.digest = archive.ingest(
            b'From: a@example.invalid\r\nSubject: migration evidence\r\n'
            b'Date: Thu, 26 Nov 2026 09:00:00 +0000\r\n\r\nneedle migration body')
        archive.db.close()
        catalog = Catalog(self.source)
        try:
            with catalog.db:
                catalog.add_file('doc-hash', 'document', 'note.txt',
                                 '/tmp/note.txt', 1, '2026-11-28')
                catalog.add_record(
                    'doc1', 'document', 'note.txt', 'document', None,
                    '2026-11-28T00:00:00+00:00', 'second', 'catalog migration needle',
                    '{}', 'doc-hash', '2026-11-28')
        finally:
            catalog.close()
        archive = Archive(self.source)
        research = Research(archive)
        try:
            research.workspace('Migration', 'synthetic migration workspace')
            research.collection_create('Migration', 'Evidence', 'synthetic collection')
        finally:
            research.close()
        store = ConversationStore(self.source)
        try:
            conversation = store.create('Migration', 'Synthetic conversation')
            store.append(conversation['id'], 'user', 'What about migration?')
            store.append(conversation['id'], 'assistant', 'Synthetic answer')
        finally:
            store.close()
        archive.db.close()
        (self.source / 'preferences.json').write_text('{"theme": "dark"}\n', encoding='utf-8')
        self.source_files = self._source_files()

    def tearDown(self):
        try:
            db.clear_session_key(self.source)
            for child in self.base.iterdir():
                db.clear_session_key(child)
        finally:
            self.tmp.cleanup()

    def _source_files(self):
        return {path.relative_to(self.source).as_posix(): path.read_bytes()
                for path in self.source.rglob('*')
                if path.is_file() and path.name != 'sync.lock'}

    def test_successful_migration_preserves_source_and_verifies_copy(self):
        destination = self.base / 'encrypted'
        backup = self.base / 'plaintext-backup'
        result = migration.migrate(self.source, destination, backup, PASSWORD)
        self.assertTrue(result['backup_verified'])
        self.assertTrue(result['restoration_verified'])
        self.assertIn('plaintext', result['warning'])
        self.assertTrue(encryption.is_encrypted_archive(destination))
        self.assertFalse(encryption.status(destination)['unlocked'])
        self.assertTrue(backup.is_dir())
        self.assertFalse(encryption.is_encrypted_archive(self.source))
        self.assertFalse(encryption.is_encrypted_archive(backup))
        self.assertEqual(self._source_files(), self.source_files)
        for name in encryption.DATABASES:
            self.assertTrue(db.is_encrypted_file(destination / name), name)
        self.assertEqual(result['destination_databases']['archive.sqlite3']['versions']['destination'],
                         migration.target_version('archive'))
        self.assertEqual(result['destination_databases']['catalog.sqlite3']['versions']['destination'],
                         migration.target_version('catalog'))
        self.assertEqual(result['destination_databases']['research.sqlite3']['versions']['destination'],
                         migration.target_version('research'))
        self.assertEqual((destination / 'raw' / (self.digest + '.eml')).read_bytes(),
                         (self.source / 'raw' / (self.digest + '.eml')).read_bytes())
        self.assertEqual((destination / 'preferences.json').read_text(),
                         (self.source / 'preferences.json').read_text())
        copy = self.base / 'copied.sqlite3'
        copy.write_bytes((destination / 'archive.sqlite3').read_bytes())
        plain = sqlite3.connect(copy)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                plain.execute('SELECT count(*) FROM sqlite_master').fetchone()
        finally:
            plain.close()
        with self.assertRaises(Exception):
            db.connect(destination / 'archive.sqlite3', key=os.urandom(db.KEY_BYTES))
        encryption.unlock(destination, PASSWORD)
        self.assertTrue(search_unified(destination, 'needle'))
        archive = Archive(destination)
        research = Research(archive)
        try:
            self.assertIn('Evidence', {c['name'] for c in research.collection_list('Migration')})
        finally:
            research.close()
        store = ConversationStore(destination)
        try:
            self.assertEqual(store.list('Migration')[0]['turns'], 2)
        finally:
            store.close()
        archive.db.close()
        encryption.lock(destination)

    def test_cli_migration_success(self):
        from hb_engine import dispatch as dispatch_module
        destination = self.base / 'encrypted-cli-success'
        backup = self.base / 'backup-cli-success'
        output = io.StringIO()
        errors = io.StringIO()
        with mock.patch('getpass.getpass', side_effect=[PASSWORD, PASSWORD]), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = dispatch_module.main([
                '--archive', str(self.source), 'migrate-encrypted',
                '--destination', str(destination), '--backup', str(backup)])
        self.assertEqual(code, 0)
        self.assertTrue(encryption.is_encrypted_archive(destination))
        self.assertFalse(encryption.status(destination)['unlocked'])
        self.assertTrue(backup.is_dir())
        self.assertIn('plaintext', errors.getvalue())
        self.assertEqual(self._source_files(), self.source_files)

    def test_existing_destination_or_backup_is_rejected(self):
        destination = self.base / 'encrypted'
        destination.mkdir()
        (destination / 'occupied').write_text('x', encoding='utf-8')
        with self.assertRaises(migration.MigrationError):
            migration.migrate(self.source, destination, self.base / 'backup', PASSWORD)
        backup = self.base / 'backup'
        backup.mkdir()
        (backup / 'occupied').write_text('x', encoding='utf-8')
        with self.assertRaises(migration.MigrationError):
            migration.migrate(self.source, self.base / 'encrypted2', backup, PASSWORD)

    def test_insufficient_storage_fails_before_writing(self):
        destination = self.base / 'encrypted'
        backup = self.base / 'backup'
        with mock.patch('hb_engine.migration.shutil.disk_usage') as usage:
            usage.return_value = mock.Mock(free=0)
            with self.assertRaises(migration.MigrationError):
                migration.migrate(self.source, destination, backup, PASSWORD)
        self.assertFalse(destination.exists())
        self.assertFalse(backup.exists())
        self.assertEqual(self._source_files(), self.source_files)

    def test_cli_rejects_mismatched_password_before_migration(self):
        from hb_engine import dispatch as dispatch_module
        destination = self.base / 'encrypted-cli'
        backup = self.base / 'backup-cli'
        with mock.patch('getpass.getpass', side_effect=[PASSWORD, 'different password']), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = dispatch_module.main([
                '--archive', str(self.source), 'migrate-encrypted',
                '--destination', str(destination), '--backup', str(backup)])
        self.assertEqual(code, 1)
        self.assertFalse(destination.exists())
        self.assertFalse(backup.exists())
        self.assertEqual(self._source_files(), self.source_files)

    def test_failed_conversion_leaves_source_and_backup_without_destination(self):
        destination = self.base / 'encrypted'
        backup = self.base / 'backup'
        with mock.patch('hb_engine.migration._export_database',
                        side_effect=RuntimeError('synthetic conversion failure')):
            with self.assertRaises(migration.MigrationError):
                migration.migrate(self.source, destination, backup, PASSWORD)
        self.assertFalse(destination.exists())
        self.assertTrue(backup.is_dir())
        self.assertFalse(list(self.base.glob('.hb-migration-*')))
        self.assertEqual(self._source_files(), self.source_files)

    def test_short_password_and_restoration_failure_are_safe(self):
        destination = self.base / 'encrypted'
        backup = self.base / 'backup'
        with self.assertRaises(encryption.EncryptionError):
            migration.migrate(self.source, destination, backup, 'short')
        self.assertFalse(destination.exists())
        self.assertFalse(backup.exists())
        with mock.patch('hb_engine.migration.backup.restore',
                        side_effect=RuntimeError('synthetic restore failure')):
            with self.assertRaises(migration.MigrationError):
                migration.migrate(self.source, destination, self.base / 'backup2', PASSWORD)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.base.glob('.hb-migration-*')))
        self.assertEqual(self._source_files(), self.source_files)


if __name__ == '__main__':
    unittest.main()
