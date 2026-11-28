# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""The root-level modules are aliases for their hb_engine counterparts."""

import importlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALIAS_RE = re.compile(r"Compatibility alias for :mod:`hb_engine\.([a-z_]+)`")


def shims():
    found = []
    for path in sorted(ROOT.glob('*.py')):
        match = ALIAS_RE.search(path.read_text(encoding='utf-8'))
        if match:
            found.append((path.stem, match.group(1)))
    return found


class CompatibilityShimTests(unittest.TestCase):
    def test_shims_are_discovered(self):
        self.assertTrue(shims(), 'no compatibility shims found; has the layout changed?')

    def test_every_shim_aliases_its_engine_module(self):
        for stem, target in shims():
            with self.subTest(module=stem):
                shim = importlib.import_module(stem)
                engine = importlib.import_module(f'hb_engine.{target}')
                self.assertIs(shim, engine,
                              f'{stem}.py should alias hb_engine.{target}')

    def test_shim_targets_exist(self):
        for stem, target in shims():
            with self.subTest(module=stem):
                self.assertTrue((ROOT / 'hb_engine' / f'{target}.py').is_file())


if __name__ == '__main__':
    unittest.main()
