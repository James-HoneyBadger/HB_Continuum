# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Packaging smoke helper: packaged-module IPC checks against the source CLI."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from dispatch import Archive

ROOT = Path(__file__).resolve().parent.parent


def load_build_engine():
    spec = importlib.util.spec_from_file_location(
        'build_engine_smoke', ROOT / 'scripts' / 'build_engine.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildEngineSmokeTests(unittest.TestCase):
    def test_ipc_smoke_finds_advanced_results_and_relationship_edge(self):
        build_engine = load_build_engine()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = Archive(root / 'archive')
            archive.ingest(
                b'From: smoke@example.invalid\r\nSubject: Smoke\r\n'
                b'Date: Mon, 01 Jan 2024 10:00:00 +0000\r\n'
                b'Message-ID: <smoke-1@example.invalid>\r\n\r\nsmokeword')
            archive.ingest(
                b'From: reply@example.invalid\r\nSubject: Re: Smoke\r\n'
                b'Date: Mon, 01 Jan 2024 11:00:00 +0000\r\n'
                b'Message-ID: <smoke-2@example.invalid>\r\n'
                b'In-Reply-To: <smoke-1@example.invalid>\r\n\r\nsmokeword')
            archive.db.close()
            result = build_engine._ipc_smoke(
                [sys.executable, str(ROOT / 'dispatch.py')], root / 'archive')
        self.assertEqual(result['advanced']['result']['total'], 2)
        self.assertGreaterEqual(len(result['graph']['result']['edges']), 1)
        self.assertEqual(result['graph']['result']['edges'][0]['threads'], 1)


if __name__ == '__main__':
    unittest.main()
