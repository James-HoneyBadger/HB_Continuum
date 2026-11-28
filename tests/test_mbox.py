# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import hashlib, tempfile, threading, unittest
from pathlib import Path
from unittest import mock

from dispatch import Archive
from hb_engine import mbox

FIXTURE = """From ada.example@example.invalid Tue Mar 14 09:15:00 2023
From: Ada Example <ada.example@example.invalid>
To: Grace Example <grace.example@example.invalid>
Subject: Fictional invoice QS-1042
Date: Tue, 14 Mar 2023 09:15:00 +0000
Message-ID: <mbox-fixture-1@example.invalid>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This message is fictional. The invoice number is QS-1042.
>From a line that must not split the message.

From grace.example@example.invalid Wed Mar 15 10:00:00 2023
From: Grace Example <grace.example@example.invalid>
Subject: Re: Fictional invoice QS-1042
Date: Wed, 15 Mar 2023 10:00:00 +0000
Message-ID: <mbox-fixture-2@example.invalid>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Acknowledged, entirely fictional. Grace Example.
"""


class MboxCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.box = self.root / 'fixture.mbox'
        self.box.write_text(FIXTURE, encoding='utf-8')
        self.archive = Archive(self.root / 'archive')

    def tearDown(self):
        self.archive.db.close()


class PreviewTests(MboxCase):
    def test_preview_reports_counts_and_dates(self):
        report = mbox.preview(self.box)
        self.assertEqual(report['messages'], 2)
        self.assertEqual(report['malformed'], 0)
        self.assertEqual(report['duplicate_messages'], 0)
        self.assertLess(report['date_first'], report['date_last'])
        self.assertEqual(report['name'], 'fixture.mbox')
        self.assertIn('not byte-identical', report['note'])

    def test_missing_file_is_rejected(self):
        with self.assertRaises(mbox.MboxError):
            mbox.preview(self.root / 'absent.mbox')

    def test_symbolic_link_is_refused(self):
        link = self.root / 'link.mbox'
        link.symlink_to(self.box)
        with self.assertRaises(mbox.MboxError):
            mbox.preview(link)


class ImportTests(MboxCase):
    def test_import_preserves_provenance_and_is_searchable(self):
        result = mbox.import_mbox(self.archive, self.box)
        self.assertEqual(result['imported'], 2)
        self.assertEqual(result['failed'], 0)
        hits = self.archive.find('invoice')
        self.assertEqual(len(hits), 2)
        origins = self.archive.db.execute(
            'SELECT account, folder, uid FROM origins ORDER BY CAST(uid AS INTEGER)').fetchall()
        self.assertEqual([row[0] for row in origins], ['mbox:fixture.mbox'] * 2)
        self.assertEqual([row[1] for row in origins], ['mbox'] * 2)
        self.assertEqual([row[2] for row in origins], ['0', '1'])

    def test_reimport_is_idempotent(self):
        mbox.import_mbox(self.archive, self.box)
        again = mbox.import_mbox(self.archive, self.box)
        self.assertEqual(again['imported'], 0)
        self.assertEqual(again['existing'], 2)
        self.assertEqual(self.archive.stats()['messages'], 2)

    def test_source_file_is_not_modified(self):
        before = hashlib.sha256(self.box.read_bytes()).hexdigest()
        mbox.import_mbox(self.archive, self.box)
        self.assertEqual(hashlib.sha256(self.box.read_bytes()).hexdigest(), before)

    def test_malformed_message_is_reported_without_aborting(self):
        real_get = mbox.mailbox.mbox.get_message

        def flaky(box, key):
            if key == list(box.keys())[1]:
                raise ValueError('synthetic parse failure')
            return real_get(box, key)

        with mock.patch.object(mbox.mailbox.mbox, 'get_message', flaky):
            result = mbox.import_mbox(self.archive, self.box)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['errors'][0]['index'], 1)
        self.assertIn('synthetic parse failure', result['errors'][0]['error'])

    def test_cancellation_keeps_what_was_already_imported(self):
        cancel = threading.Event()
        seen = []

        def progress(done, imported, existing, failed):
            seen.append(done)
            cancel.set()

        result = mbox.import_mbox(self.archive, self.box, progress=progress,
                                  cancel_event=cancel)
        self.assertTrue(result['cancelled'])
        self.assertEqual(result['imported'], 1)
        self.assertEqual(seen, [1])
        self.assertEqual(self.archive.stats()['messages'], 1)


if __name__ == '__main__':
    unittest.main()
