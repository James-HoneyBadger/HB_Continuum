---
mode: agent
model: DeepSeek 4.1 Flash
description: Reconcile implementation status, release notes, and tagged code
tools: ['codebase', 'search', 'editFiles', 'runCommands', 'changes', 'problems']
---

# Task: reconcile documentation with the tagged release

You are a technical writer and release auditor for HB Continuum.

## Problem

The implementation-status document marks several v0.5 capabilities as "working tree,
uncommitted": background-thread GUI search, portable scheduling, local AI summarisation,
unified search, and the desktop IPC engine. The release notes present these as delivered.
This mismatch destroys trust in both documents.

## Do this

1. **Build an inventory table** with one row per ambiguous feature, columns:
   `Feature | Release-note claim | Status-doc claim | Code present in tag? | Tests present?`
   Verify "code present" by actually searching the tree and the test suite — cite file paths
   and test names. Do not guess.

2. **Decide per feature**, using this framework, and state the reasoning in one sentence each:
   - **(a) Commit it** — code exists, tests exist, behaviour is stable → mark Implemented.
   - **(b) Flag-gate it** — code exists but is unstable or untested → mark Experimental and
     ensure an explicit config flag guards it.
   - **(c) Withdraw the claim** — code is absent from the tag → remove from release notes,
     keep as Not yet committed.

3. **Rewrite `IMPLEMENTATION_STATUS.md`** using exactly three states:
   `Implemented`, `Experimental (flag-gated)`, `Not yet committed`.
   Every row must name the verifying test file or the config flag that gates it.

4. **Add a CI guard.** Write `scripts/check_doc_fidelity.py` (standard library only) that:
   - parses `IMPLEMENTATION_STATUS.md`
   - parses the release-notes file for feature bullets
   - fails with exit code 1 if a release note claims a feature that is not marked
     `Implemented` or `Experimental`
   - prints a clear diff-style report of mismatches
   Add the invocation to `.github/workflows/` as a lightweight job. Include a unit test
   for the script under `tests/`.

## Constraints

- Standard library only for the script (no new dependencies).
- Do not change product code in this task — this is a documentation-and-CI task.
- If a feature genuinely cannot be verified from the tree, mark it `Not yet committed`
  rather than inventing evidence.

## Acceptance criteria

- Inventory table with file/test citations.
- Rewritten `IMPLEMENTATION_STATUS.md` with only the three allowed states.
- `scripts/check_doc_fidelity.py` plus its unit test, both passing locally.
- One workflow job added, shown as a diff.
