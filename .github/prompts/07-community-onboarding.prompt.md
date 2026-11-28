---
mode: agent
model: DeepSeek 4.1 Flash
description: Add contributor infrastructure and lower the barrier to entry
tools: ['codebase', 'search', 'editFiles', 'runCommands', 'githubRepo']
---

# Task: build community onboarding infrastructure

You are a developer advocate for HB Continuum. The repository has one star, zero forks, and
no external contributors. The goal is to make it easy for technically comfortable users and
security researchers to help — without lowering the project's security bar.

## Do this

1. **Write `CONTRIBUTING.md`:**
   - Development environment: Python 3.12+, Node, Rust, optional SQLCipher; the exact
     install commands per OS.
   - How to run tests, including the SQLCipher and non-SQLCipher variants and the expected
     counts. State that `mypy` must be clean.
   - Branch strategy: feature branches off the development branch; squash merge to `main`;
     conventional commit prefixes.
   - Coding standards: standard-library-first, import-guarded optional deps, fail-closed
     error handling, tests for every behaviour change.
   - **Security path:** a prominent boxed link to `SECURITY.md` stating that
     security-sensitive changes must be discussed privately before any public PR.
   - A short "what we will not merge" list: telemetry, mandatory cloud calls, silent
     credential fallbacks, undocumented out-of-boundary writes.

2. **Issue templates** under `.github/ISSUE_TEMPLATE/`:
   - `bug_report.yml` — OS, Python version, SQLCipher on/off, desktop shell, steps to
     reproduce, and a mandatory checkbox confirming **synthetic data only**.
   - `feature_request.yml` — problem statement, proposed behaviour, privacy/security impact
     assessment (required field), alternatives considered.
   - `config.yml` — blank issues disabled; `contact_links` routing security to
     `SECURITY.md` and questions to Discussions.

3. **Discussions guidance:** write a short `.github/DISCUSSIONS.md` describing recommended
   categories: Q&A, Show and tell, Platform testing reports, Security hardening ideas,
   Ideas. State that vulnerability details never belong in Discussions.

4. **Quickstart scripts:** `scripts/quickstart.sh` and `scripts/quickstart.ps1` that create
   a disposable archive in a temp directory, import a synthetic fixture EML, run a search,
   verify integrity, print the result, and clean up. Idempotent, no network, no writes
   outside the temp dir. Mirror the tutorial's "start with fictional data" guidance.

5. **Seed the backlog** with five concrete "good first issue" proposals, each with a file
   path, a one-line description, and a definition of done. Prefer: missing docstrings in
   `catalog`, an edge-case test for import deduplication, clearer error text when SQLCipher
   is absent, a fixtures cleanup, and a README typo sweep. Do not propose security-critical
   work as good-first-issue.

## Constraints

- No new dependencies for the quickstart scripts.
- Templates must not encourage pasting real email content.
- Do not create files that duplicate existing ones — check first and extend instead.

## Acceptance criteria

- `CONTRIBUTING.md`, three issue-template files, `DISCUSSIONS.md`, two quickstart scripts,
  and a list of five good-first issues with definitions of done.
- Both quickstart scripts run clean on a fresh checkout (show the output).
