# Benchmarks

`scripts/benchmark.py` builds a deterministic synthetic archive, measures the
operations that matter for a large personal archive, and prints a table plus
JSON. It never uses a real archive.

## Reproducing

```sh
# Temporary archives, removed afterwards (default: 10,000 records)
python3 scripts/benchmark.py --sizes 10000

# Two sizes and a saved JSON result
python3 scripts/benchmark.py --sizes 10000,100000 --json bench.json

# Keep the synthetic archives for inspection
python3 scripts/benchmark.py --sizes 10000 --workdir /tmp/hb-bench --keep

# Also time a full byte-level health scan
python3 scripts/benchmark.py --sizes 10000 --health
```

Safety rules:

- Without `--workdir`, archives are created in a fresh temporary directory and
  deleted unless `--keep` is passed.
- An explicit `--workdir` must be empty. The script never deletes or reuses an
  existing directory that contains files.
- `--json` refuses to replace an existing result file.

## What is measured

| Metric | Meaning |
|---|---|
| `ingest` | `Archive.ingest` per synthetic message: raw file write plus FTS and metadata transaction |
| `find` | 20 deterministic FTS5 queries, 50 results each (p50/p95/mean) |
| `unified_search` | The same 20 queries through unified search |
| `timeline.first_page_ms` | First 100 records by normalized timestamp |
| `timeline.deep_page_ms` | 100 records at the end of the archive (offset `count - 100`) |
| `timeline.reverse_page_ms` | Newest-first first page |
| `dashboard_ms` | Summary, year buckets and storage footprint |
| `max_rss_mib` | Peak resident memory of the whole process |

Synthetic messages carry RFC 2822 dates spread across years, 250 synthetic
senders and a fixed vocabulary. Records are deterministic for a given
`--seed`.

## Baseline results

Recorded 2026-11-27 on the development machine:

- macOS 27.3, Apple ARM64, 18 CPUs
- Python 3.13.6
- Local SSD; results include filesystem writes and fsync per original

| messages | ingest s | msg/s | raw MiB | db MiB | find p50 ms | find p95 ms | timeline first ms | timeline deep ms | dashboard ms | max RSS MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| 10,000 | 9.8 | 1,021 | 4.6 | 15.2 | 0.1 | 0.1 | 0.1 | 3.7 | 5.1 | 46.8 |
| 100,000 | 150.1 | 666 | 45.9 | 151.9 | 0.1 | 0.1 | 0.1 | 34.6 | 33.9 | 77.8 |

These are single runs on one machine and one filesystem. Treat them as a
regression baseline, not a specification.

## Observations

- Full-text search is effectively sub-millisecond at both sizes because FTS5
  answers from its index.
- The first timeline page is constant-time. A deep page grows with the offset
  (3.7 ms at 10k, 34.6 ms at 100k) because SQLite walks the `sort_ts` index to
  the requested offset; it does not load the archive into memory.
- Storage accounting previously walked every raw file on each dashboard
  refresh (about 699 ms at 100k). Archive schema 5 records each original's
  size at import, bringing the same dashboard to about 34 ms. Archives that
  predate the column, or contain records whose original is missing, keep the
  filesystem fallback.
- Ingest is dominated by durable file writes and one transaction per message,
  so throughput depends heavily on the filesystem. It is not a CPU bound.
- 1,000,000-record runs have not been performed; do not claim support for that
  size without measuring it.

## Recording a new baseline

1. Run the command above on the target machine with `--json`.
2. Keep the JSON with the machine description.
3. Compare like with like: same sizes, same seed, same storage, no concurrent
   work.
4. Update this file with the machine and results, and note any code change
   that explains a difference.
