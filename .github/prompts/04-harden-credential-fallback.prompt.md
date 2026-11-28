---
mode: agent
model: DeepSeek 4.1 Flash
description: Audit and harden the credential-storage path (fail closed)
tools: ['codebase', 'search', 'usages', 'editFiles', 'runCommands', 'findTestFiles', 'problems']
---

# Task: harden the credential-storage fallback

You are a security engineer reviewing credential handling in HB Continuum. The portable
scheduler prefers the OS keyring (SecretService / macOS Keychain / Windows Credential
Manager) but also supports an "encrypted-file fallback". A lower-security fallback that
engages silently is a liability for an archive holding a lifetime of personal data.

## Do this

1. **Trace every credential path.** Use `usages` and `search` across `hb_engine/` —
   start from `schedulers.py`, `encryption.py`, `db.py`, and any config loader. For each
   read/write of a secret, record in a table:
   `Location | Secret type | Backend (keyring | encrypted file | plaintext) | Trigger condition`
   Cite line numbers. Do not assume — follow the call graph.

2. **Write the threat model** for the encrypted-file fallback. Answer precisely:
   - What key encrypts the fallback file?
   - Where does that key come from, and where is it stored?
   - Can an attacker with local read access to the archive directory recover the credential?
   - Can an attacker with write access silently swap the fallback for a weaker one?
   - What happens on tamper: is the ciphertext authenticated (AEAD tag) or not?

3. **Recommend one remediation** and justify it:
   - **(A) Remove the fallback; fail closed** with an actionable error naming the missing
     keyring backend and the platform fix.
   - **(B) Opt-in only:** gate behind `--allow-insecure-credential-fallback`, emit a
     prominent startup warning, document the trade-off in `SECURITY.md`.
   - **(C) Redesign:** derive the fallback key from a user passphrase with Argon2id
     (state parameters), store only an AEAD ciphertext blob, and detect tampering.
   Default to (A) unless you find a concrete use case that makes the tool unusable.

4. **Implement the chosen option**, including the error messages. Error text must tell the
   user what is wrong and what to do — not just "keyring unavailable".

5. **Add tests** covering: keyring success; keyring unavailable with fallback disabled
   (expect fail-closed); keyring unavailable with fallback enabled under option B;
   tamper detection on the fallback blob (flip a byte, expect a clean error, no plaintext
   leakage); and a regression test that no plaintext secret is ever written to disk
   (scan the temp archive directory).

## Constraints

- Fail closed by default. No silent downgrade, ever.
- Optional crypto dependencies must be import-guarded; core must still import cleanly
  without them.
- Do not log secrets at any level, including debug.
- Keep `mypy` clean.

## Acceptance criteria

- Credential-path table with line citations.
- Written threat model answering all five questions.
- Implemented remediation with a diff.
- Five new tests, all passing, with the SQLCipher and non-SQLCipher variants both green.
- No plaintext secret written to disk in any test run.
