---
mode: agent
model: DeepSeek 4.1 Flash
description: Add SECURITY.md and enable private vulnerability reporting
tools: ['codebase', 'editFiles', 'fetch', 'runCommands']
---

# Task: establish a security disclosure policy

You are the security maintainer for HB Continuum, a local-first archive holding sensitive
personal email and documents. The repo has no `SECURITY.md` and no private reporting path.

## Do this

1. **Write `SECURITY.md`** at the repository root containing:
   - A one-paragraph statement that the project handles sensitive personal data and takes
     reports seriously, scoped honestly to a single-maintainer beta.
   - **Supported versions** table: `v0.5.x` receives security fixes; `v0.4.x` and earlier
     receive none. State that betas may change format and guarantees without notice.
   - **How to report:** GitHub Security → "Report a vulnerability" (private vulnerability
     reporting). Explicitly instruct reporters NOT to open public issues, PRs, or
     discussions for vulnerabilities.
   - **Response expectations:** acknowledgement within 72 hours, initial assessment within
     7 days, best-effort fix timeline. Say plainly that this is not an enterprise SLA.
   - **Disclosure:** coordinated disclosure; credit given unless anonymity is requested.
   - **In scope:** engine core (`hb_engine/`), encryption and key handling, credential
     storage, import/export integrity, the Tauri IPC boundary.
   - **Out of scope:** third-party dependencies (report upstream), OS-level issues,
     full-disk-encryption failures, and data outside the documented encryption boundary.
   - **Explicit non-guarantees:** raw EML files, external documents, config, and exports
     are outside the encrypted database boundary — repeat this here so reporters are not
     surprised.

2. **Enablement steps:** list the exact click-path and the `gh api` equivalent to turn on
   private vulnerability reporting for the repository. Mark as "human executes".

3. **README badge:** add a security badge near the top of `README.md` linking to
   `SECURITY.md`, and a one-line pointer in the "Getting started" section.

4. **Cross-link:** reference `SECURITY.md` from `CONTRIBUTING.md` if it exists, and from the
   issue-template chooser config (`.github/ISSUE_TEMPLATE/config.yml`) with a
   `contact_links` entry that routes security questions away from public issues.

## Constraints

- Concise and realistic. No promises the maintainer cannot keep.
- No invented email addresses, PGP keys, or bug-bounty programmes.
- Do not claim an audit has occurred.

## Acceptance criteria

- `SECURITY.md` committed with all sections above.
- README badge diff.
- `.github/ISSUE_TEMPLATE/config.yml` contact link diff.
- A short "human must do" list for repository settings.
