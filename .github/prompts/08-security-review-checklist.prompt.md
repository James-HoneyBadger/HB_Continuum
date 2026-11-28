---
mode: agent
model: DeepSeek 4.1 Flash
description: Package the encryption and credential paths for external security review
tools: ['codebase', 'search', 'editFiles', 'runCommands', 'findTestFiles']
---

# Task: create an external security-review package

You are preparing HB Continuum for its first independent audit. Make it easy for an outside
researcher to do a focused review of the two most sensitive areas without reading the whole
codebase.

## Do this

1. **Write `SECURITY_REVIEW_CHECKLIST.md`** containing:
   - **Scope:** exact files and modules for encryption (`hb_engine/encryption.py`, `db.py`,
     SQLCipher integration, backup/restore) and credential handling (`schedulers.py`,
     keyring integration). Explicitly out of scope for pass one: Vue frontend, Tauri shell,
     third-party dependencies, packaging.
   - **Threat-model prompts** the reviewer must answer, at minimum:
     - Can an attacker with read access to the archive directory recover plaintext without
       the key?
     - How is the SQLCipher key obtained — passphrase-derived or keyring-stored? Which KDF,
       which parameters, which salt handling?
     - What happens when the OS keyring is unavailable — fail closed, or fall back? Where
       is that decision made in code?
     - Which data is outside the encryption boundary, and is that surfaced in-app?
     - Can the backup path leak plaintext, and is a restore verified before overwrite?
     - Is the AEAD usage correct — unique nonces, authenticated associated data, no reuse?
   - **Test vectors:** a reproducible recipe — disposable archive with a stated passphrase,
     a synthetic fixture EML, the expected SHA-256 of the original bytes — so the reviewer
     can confirm encryption, backup, and restore behave as documented. Include the exact
     commands.
   - **Reporting template:** severity (Critical/High/Medium/Low), component, reproduction
     steps, impact, suggested remediation, and whether the reporter wants credit.
   - **Response expectations:** restate the `SECURITY.md` commitments verbatim.

2. **Prepare the test-vector artefacts:** create `tests/fixtures/security_review/` with a
   synthetic EML (obviously fictional names and content), a `README.md` stating the expected
   hashes, and a script `scripts/security_review_vectors.sh` that reproduces the archive,
   exercises encrypt → backup → restore → verify, and prints pass/fail per step.

3. **Verify it actually works.** Run the vector script end to end with SQLCipher enabled and
   with it disabled, and paste the output. If a step cannot pass, fix the script or
   document the gap — do not ship a broken vector.

4. **Link it in:** add a "Security review" section to `CONTRIBUTING.md` and a line in
   `SECURITY.md` pointing reviewers at the checklist.

## Constraints

- Fixtures must be unmistakably fictional.
- The vector script must not require network access.
- Do not weaken encryption parameters to make a test pass.

## Acceptance criteria

- `SECURITY_REVIEW_CHECKLIST.md` with scope, prompts, vectors, template, and SLA.
- Fixture directory plus vector script.
- Pasted output of both runs (SQLCipher on and off).
- Cross-links added.
