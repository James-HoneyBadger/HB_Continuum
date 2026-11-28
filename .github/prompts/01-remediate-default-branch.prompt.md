---
mode: agent
model: DeepSeek 4.1 Flash
description: Bring main up to v0.5.0-beta and fix release/onboarding drift
tools: ['codebase', 'search', 'runCommands', 'editFiles', 'changes', 'githubRepo']
---

# Task: remediate the stale default branch

You are a release engineer for the HB Continuum repository (local-first personal archive;
Python standard-library core, SQLCipher encryption, Tauri 2 + Vue 3 desktop shell).

## Problem

The default branch `main` still reflects the v0.3 "Dispatch-era" baseline. Its README
advertises `v0.4.0-beta`. The actual current release is `v0.5.0-beta`, which lives on a
development branch (`develop/intelligence-update`). Pull request #10 exists to bring v0.5
onto `main` and is still open. A user who clones the default branch gets the wrong code.

## Do this

1. **Establish ground truth first.** Inspect the repo and report:
   - output of `git describe --tags` on each relevant branch
   - the commit SHA that `v0.5.0-beta` points to
   - whether `develop/intelligence-update` is a fast-forward from `main` or has diverged
   - the file count and test count expected on the correct tag
   Do not proceed until you have stated these facts.

2. **Recommend a merge strategy** for PR #10: squash, rebase-then-merge, or fast-forward.
   State the trade-offs, and say explicitly whether the PR should be rebased or merged
   as-is. If the divergence is large, propose a two-step plan (land v0.5, then a follow-up
   cleanup commit).

3. **Draft the branch ruleset** for `main`: allow only squash merges, require linear
   history, forbid deletion and force-push, require CI green before merge, require the
   PR template to be filled. Give the exact `gh api` or `gh ruleset` commands, marked as
   "human executes".

4. **Fix `README.md`** on `main`: correct the version badge, the branch guidance, and the
   quick-start commands so they match `v0.5.0-beta`. Remove every reference to
   `v0.4.0-beta` and older. Add a short "Which branch should I use?" section.

5. **Tag hygiene:** verify `v0.5.0-beta` points at the intended commit; if not, propose the
   correction (do not run it). Confirm the release page is linked from the README.

6. **Write a verification checklist** a new user can follow after cloning to confirm they
   are on the right code: expected `git describe` output, expected test count, expected
   presence of `hb_engine/encryption.py`, and a one-line command that proves v0.5 is live.

## Constraints

- Do NOT run `git push`, `git push --force`, `git tag -d`, or any remote-mutating command.
  Print them for the human to run.
- Do NOT rewrite public history.
- Keep README edits minimal and factual; no marketing language.

## Acceptance criteria

- A stated ground-truth table (branch → tag → SHA → test count).
- A merge recommendation with rationale.
- A diff for `README.md`.
- A numbered verification checklist.
- Zero remote-mutating commands executed.
