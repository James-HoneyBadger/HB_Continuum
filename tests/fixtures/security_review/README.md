# Security review fixtures

Synthetic records for [SECURITY_REVIEW_CHECKLIST.md](../../../SECURITY_REVIEW_CHECKLIST.md).
Every name, address and reference here is fictional.

## `fictional-2023-03-14.eml`

| Property | Value |
| --- | --- |
| Size | 595 bytes |
| SHA-256 | `653eef314e3ce4374eff51724ecd6d75a4c82370262a409030329f3fe78919f2` |
| Message-ID | `security-review-fixture-0001@example.invalid` |
| Expected search hit | `invoice` |

Verify the fixture is unmodified:

```sh
shasum -a 256 tests/fixtures/security_review/fictional-2023-03-14.eml
# 653eef314e3ce4374eff51724ecd6d75a4c82370262a409030329f3fe78919f2
```

Run `scripts/security_review_vectors.sh` to exercise import, encryption, backup,
restore and verification against a disposable archive.
