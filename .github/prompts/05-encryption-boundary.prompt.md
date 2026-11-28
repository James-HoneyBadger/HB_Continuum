---
mode: agent
model: DeepSeek 4.1 Flash
description: Make the encryption boundary explicit to users and assess extending it
tools: ['codebase', 'search', 'editFiles', 'runCommands', 'fetch']
---

# Task: clarify and, where feasible, extend the encryption boundary

You are a documentation and security engineer for HB Continuum. SQLCipher encrypts the
SQLite database, but raw EML files, external documents, configuration, and exports sit
outside that boundary. Users routinely assume "encrypted archive" means everything.

## Do this

1. **Produce the boundary table.** One row per data category:
   `SQLite database`, `raw EML store`, `external document directory`, `FTS5 indexes`,
   `config files`, `credential store`, `exports`, `logs`, `backups`.
   Columns: `Inside SQLCipher boundary? | Where it lives | Recommended supplementary control`.
   Verify each claim from the code — do not copy from release notes without checking.

2. **Draft the in-app warning** shown at archive creation and at first unlock, under 150
   words. It must: state that the database is encrypted; list what is not; recommend
   OS full-disk encryption or an encrypted container; and offer a "don't show again"
   acknowledgement that is itself logged. Plain language, no jargon.

3. **Feasibility assessment** for bringing the raw EML store and document directory inside
   an encrypted container. Consider: SQLCipher attached databases, a separate encrypted
   volume, or an encrypted blob store with per-file AEAD. For each option state the impact
   on: FTS5 indexing, streaming reads of large EML files, backup/restore, migration cost,
   and the ability to read files externally. Give a verdict per option:
   **feasible now / feasible later / not feasible**. If not feasible in the near term, say
   so plainly and record it as a known limitation.

4. **Update the encryption-migration tutorial** to include the boundary table, the warning
   text, and the supplementary-control recommendations. Add a "What encryption does not
   cover" section near the top, not buried at the end.

5. **Code check:** confirm every writer that touches out-of-boundary data has a docstring
   line naming the boundary. List any missing ones and add them.

## Constraints

- Honesty over reassurance. Do not soften the limitation.
- No new mandatory dependencies for the feasibility work — this task is analysis plus docs
  plus docstrings.
- If you propose an implementation, scope it as a separate follow-up issue, not a patch in
  this change.

## Acceptance criteria

- Boundary table with code-verified claims.
- Warning copy under 150 words, plus where it is displayed.
- Feasibility verdict per option with impact analysis.
- Tutorial diff.
- List of docstrings added or corrected.
