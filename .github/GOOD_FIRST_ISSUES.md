# Good first issues

Proposals for a newcomer's first pull request. Each is small, self-contained
and testable. None touches encryption, key handling or credential storage:
those need private discussion first (see [SECURITY.md](../SECURITY.md)).

Create an issue from one of these when you start, so two people do not do the
same work.

## 1. Document the catalog public methods

- **File:** `hb_engine/catalog.py`
- **Change:** add docstrings to the public methods (`add_file`, `has_file`,
  `add_record`, `search`, and the verify helpers) stating parameters, return
  values and whether each writes.
- **Done when:** `mypy` is clean, `python3 -m unittest tests.test_facebook
  tests.test_sources` still passes, and no behaviour changes.

## 2. Cover re-import of identical bytes

- **File:** `tests/test_dispatch.py`
- **Change:** add a test that imports one synthetic EML twice in the same
  archive and asserts the second run reports it as existing, that one raw file
  remains, and that the index still returns a single hit.
- **Done when:** the test fails if deduplication is disabled, and the full
  suite passes.

## 3. Name the install command when SQLCipher is missing

- **File:** `hb_engine/db.py`
- **Change:** the `EncryptionUnavailable` message explains that no plaintext
  fallback was attempted but not how to fix it. Add the install command and the
  platform note from `docs/PACKAGING.md`.
- **Done when:** a test asserts the message contains the install command, and
  the message still makes no attempt to open the database in plaintext.

## 4. Audit the test fixtures

- **Directories:** `tests/fixtures/`
- **Change:** list every fixture, note which tests use it, and remove or
  document the unused ones. The security-review fixture must keep its recorded
  SHA-256.
- **Done when:** every remaining file has a named consumer, and the suite
  counts match what `CONTRIBUTING.md` documents.

## 5. Broken-link and typo sweep

- **Files:** `README.md`, `docs/*.md`, `CONTRIBUTING.md`
- **Change:** check every relative link resolves and correct obvious spelling
  errors. Do not reword technical claims.
- **Done when:** a small script or manual pass shows no broken links and
  `python3 scripts/check_doc_fidelity.py` still passes.
