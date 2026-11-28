"""Tests for scripts/check_doc_fidelity.py."""

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "check_doc_fidelity", ROOT / "scripts" / "check_doc_fidelity.py")
assert SPEC and SPEC.loader
fidelity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fidelity)

INVENTORY = """# Status

| Feature | Key | State | Evidence |
| --- | --- | --- | --- |
| Search | `unified-search` | Implemented | `tests/test_unified.py` |
| MBOX | `mbox-io` | Not yet committed | No code in the tag |
| PDF | `pdf-extract` | Experimental (flag-gated) | `pypdf` |
"""


class FixtureCase(unittest.TestCase):
    def build(self, release_text, inventory=INVENTORY):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "docs" / "engineering").mkdir(parents=True)
        (root / "docs" / "releases").mkdir(parents=True)
        (root / "docs" / "engineering" / "IMPLEMENTATION_STATUS.md").write_text(
            inventory, encoding="utf-8")
        (root / "docs" / "releases" / "v1.md").write_text(release_text, encoding="utf-8")
        return root


class PassingCase(FixtureCase):
    def test_implemented_and_experimental_claims_pass(self):
        root = self.build(
            "- Search works <!-- claim: unified-search -->\n"
            "- PDF extraction <!-- claim: pdf-extract -->\n")
        errors, report = fidelity.check(root)
        self.assertEqual(errors, [])
        self.assertEqual(len(report), 2)

    def test_repository_documentation_passes(self):
        errors, report = fidelity.check(ROOT)
        self.assertEqual(errors, [])
        self.assertTrue(report)


class FailingCase(FixtureCase):
    def test_claim_for_uncommitted_feature_fails(self):
        root = self.build("MBOX import <!-- claim: mbox-io -->\n")
        errors, _ = fidelity.check(root)
        self.assertEqual(len(errors), 1)
        self.assertIn("mbox-io", errors[0])
        self.assertIn("Not yet committed", errors[0])

    def test_unknown_claim_fails(self):
        root = self.build("Something <!-- claim: not-inventoried -->\n")
        errors, _ = fidelity.check(root)
        self.assertTrue(any("not in the inventory" in error for error in errors))

    def test_release_without_markers_fails(self):
        root = self.build("No markers here.\n")
        errors, _ = fidelity.check(root)
        self.assertTrue(any("no " in error and "markers" in error for error in errors))

    def test_disallowed_state_fails(self):
        inventory = INVENTORY.replace("Implemented | `tests/test_unified.py`",
                                      "Working tree | `tests/test_unified.py`")
        root = self.build("- Search <!-- claim: unified-search -->\n", inventory)
        errors, _ = fidelity.check(root)
        self.assertTrue(any("is not one of" in error for error in errors))

    def test_missing_evidence_fails(self):
        inventory = INVENTORY.replace("Implemented | `tests/test_unified.py`", "Implemented |")
        root = self.build("- Search <!-- claim: unified-search -->\n", inventory)
        errors, _ = fidelity.check(root)
        self.assertTrue(any("no verifying test" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
