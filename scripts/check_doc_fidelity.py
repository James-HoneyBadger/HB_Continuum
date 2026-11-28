#!/usr/bin/env python3
"""Verify that release notes do not claim capabilities missing from the inventory.

Release notes under ``docs/releases/`` mark each claim with an HTML comment
``<!-- claim: some-key -->``. Every claimed key must appear in
``docs/engineering/IMPLEMENTATION_STATUS.md`` with the state ``Implemented`` or
``Experimental (flag-gated)``.

Standard library only. Exits 1 and prints a diff-style report on mismatch.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "docs" / "engineering" / "IMPLEMENTATION_STATUS.md"
RELEASES = ROOT / "docs" / "releases"

ALLOWED_STATES = ("Implemented", "Experimental (flag-gated)", "Not yet committed")
CLAIMED_STATES = ("Implemented", "Experimental (flag-gated)")

CLAIM_RE = re.compile(r"<!--\s*claim:\s*([A-Za-z0-9_.-]+)\s*-->")
ROW_RE = re.compile(r"^\|\s*(?P<feature>[^|]*?)\s*\|\s*`(?P<key>[A-Za-z0-9_.-]+)`\s*\|"
                    r"\s*(?P<state>[^|]*?)\s*\|\s*(?P<evidence>[^|]*?)\s*\|\s*$", re.MULTILINE)


def parse_status(text: str) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Return {key: (state, evidence)} and a list of inventory problems."""
    inventory: dict[str, tuple[str, str]] = {}
    problems: list[str] = []
    for match in ROW_RE.finditer(text):
        key = match.group("key")
        state = match.group("state")
        evidence = match.group("evidence")
        if state not in ALLOWED_STATES:
            problems.append(f"{key}: state {state!r} is not one of {ALLOWED_STATES}")
        elif not evidence:
            problems.append(f"{key}: no verifying test or flag recorded")
        if key in inventory:
            problems.append(f"{key}: duplicate inventory row")
        inventory[key] = (state, evidence)
    if not inventory:
        problems.append("no inventory rows found; expected a table with a `key` column")
    return inventory, problems


def parse_claims(text: str) -> list[tuple[int, str]]:
    claims = []
    for match in CLAIM_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        claims.append((line, match.group(1)))
    return claims


def check(root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, report lines) for the documentation under *root*."""
    status_path = root / "docs" / "engineering" / "IMPLEMENTATION_STATUS.md"
    releases_dir = root / "docs" / "releases"
    errors: list[str] = []
    report: list[str] = []

    if not status_path.is_file():
        return [f"missing inventory: {status_path.relative_to(root)}"], report
    inventory, problems = parse_status(status_path.read_text(encoding="utf-8"))
    errors.extend(problems)

    release_files = sorted(releases_dir.glob("*.md")) if releases_dir.is_dir() else []
    if not release_files:
        errors.append("no release notes found under docs/releases/")

    for release in release_files:
        rel = release.relative_to(root)
        claims = parse_claims(release.read_text(encoding="utf-8"))
        if not claims:
            errors.append(f"{rel}: no <!-- claim: key --> markers found")
        for line, key in claims:
            entry = inventory.get(key)
            if entry is None:
                errors.append(f"{rel}:{line}: claim {key!r} is not in the inventory")
                continue
            state = entry[0]
            if state not in CLAIMED_STATES:
                errors.append(
                    f"{rel}:{line}: claim {key!r} is {state!r}; release notes may only "
                    f"claim {CLAIMED_STATES}")
                continue
            report.append(f"ok   {rel}:{line} {key} -> {state}")
    return errors, report


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]).resolve() if argv else ROOT
    errors, report = check(root)
    for line in report:
        print(line)
    if errors:
        print()
        for error in errors:
            print(f"MISMATCH {error}")
        print(f"\n{len(errors)} documentation fidelity problem(s).")
        return 1
    print(f"\n{len(report)} claim(s) verified against the inventory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
