# v0.6 refinement baseline

Recorded before changes in this milestone. "Verified" means reproduced or
confirmed from the tree; "suspected" means plausible but not demonstrated.

## Repository state at the start

- Default branch `main` at `5b9f622`, which is also `v0.5.0-beta`.
- Development branch for this milestone: `develop/v0.6-refinement`, branched
  from `docs/doc-fidelity` (the unmerged remediation work).
- Working tree clean before starting; `build/` and `dist/` are ignored
  PyInstaller output.
- Engine: `hb_engine/` (23 modules), root-level compatibility shims, Tk shell,
  `frontend/` (Vue 3), `src-tauri/` (Tauri 2).

## Test baseline

| Variant | Result |
| --- | --- |
| Python 3.12, no `sqlcipher3` | 371 tests, OK, 24 skipped |
| Python 3.12, with `sqlcipher3` | 371 tests, OK, 7 skipped |
| `mypy` (30 files) | clean |
| `scripts/check_doc_fidelity.py` | 6 claims verified |
| `scripts/security_review_vectors.sh` | 14 passed with SQLCipher, 0 failed |

## Verified defects

| # | Defect | Where | State |
| --- | --- | --- | --- |
| 1 | Credential fallback engaged silently when no OS keyring existed | `hb_engine/schedulers.py` | Fixed in this branch |
| 2 | Corrupt `credentials.enc` raised a raw `JSONDecodeError` | `hb_engine/schedulers.py` | Fixed in this branch |
| 3 | `mypy` failed for developers who had `sqlcipher3` installed | `hb_engine/migration.py`, `mypy.ini` | Fixed in this branch |
| 4 | Implementation status claimed working features were "uncommitted" | `docs/engineering/` | Fixed in this branch |
| 5 | Release notes described encrypted creation as a desktop feature | release body | Fixed in this branch |
| 6 | Branch protection required check names the matrix no longer emitted | repository settings | Fixed at repository level |
| 7 | `v0.5.0-beta` pointed at a commit older than the documented source | git tag | Fixed at repository level |
| 8 | No `SECURITY.md`, no disclosure route | repository root | Fixed in this branch |
| 9 | Encryption boundary not surfaced in the application | `frontend/src/App.vue` | Fixed in this branch |

## Suspected weaknesses, not yet demonstrated

- Root-level compatibility shims duplicate module names with `hb_engine/`; a
  stale shim could shadow a newer implementation. Not reproduced.
- `docs/QUALIFICATION_LOG.md` retains historical counts that no longer match
  the suite; it is labelled historical, but a reader may still trust it.
- Backup of an encrypted archive copies `raw/` and configuration in plaintext.
  Documented; not a defect, but a persistent surprise risk.
- Ollama integration has no automated test against a live model.
- No packaged desktop build is produced for Linux or Windows.

## Environment limits recorded honestly

- The default `python3` on this machine (pyenv 3.13.6) has an incomplete
  standard library: `import tomllib` fails with `No module named
  'tomllib._types'`. The suite reports one import error under that
  interpreter. Verification here used a clean Python 3.12 framework build.
- No PowerShell is available, so `scripts/quickstart.ps1` is unexecuted.
- No Linux or Windows desktop artefact can be produced locally.
