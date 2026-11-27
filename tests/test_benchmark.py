# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""The synthetic benchmark harness itself is deterministic and safe."""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import benchmark  # noqa: E402

class BenchmarkTests(unittest.TestCase):
    def test_generator_is_deterministic_and_unique(self):
        first=list(benchmark.generate_messages(20))
        second=list(benchmark.generate_messages(20))
        self.assertEqual(first,second)
        self.assertEqual(len(set(first)),20)
        self.assertIn(b'Date: ',first[0])

    def test_small_run_measures_ingest_search_and_timeline(self):
        result=benchmark.run_size(150,seed=7,cleanup=True)
        self.assertEqual(result['messages'],150)
        self.assertGreater(result['ingest']['seconds'],0)
        self.assertGreater(result['storage']['raw_bytes'],0)
        self.assertEqual(result['timeline']['first_page_rows'],100)
        self.assertEqual(result['timeline']['deep_offset'],50)
        self.assertEqual(result['timeline']['deep_page_rows'],100)
        self.assertEqual(result['timeline']['reverse_page_rows'],100)
        self.assertGreater(result['dashboard']['by_year_buckets'],0)
        self.assertEqual(result['dashboard']['undated'],0)
        self.assertIsNotNone(result['find']['p50_ms'])

    def test_workdir_must_be_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'keep.txt').write_text('x')
            with self.assertRaises(SystemExit):
                benchmark.prepare_workdir(tmp)

    def test_table_renders_all_rows(self):
        result=benchmark.run_size(10,seed=3,cleanup=True)
        table=benchmark.render_table([result])
        self.assertIn('| messages |',table)
        self.assertIn('| 10 |',table)

if __name__=='__main__':
    unittest.main()
